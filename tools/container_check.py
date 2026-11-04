"""Independent checks for this mod's UE4 directory-index IoStore packages.

Reads and decompresses every block, then reconstructs each chunk using the TOC.
This supports the unencrypted, unsigned v3 packages produced by our packager.
It does not certify the game's package dependency or spawn behavior.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import struct
import zlib


def unpack(toc: bytes, data: bytes) -> dict[bytes, bytes]:
    if len(toc) < 144 or toc[:16] != b"-==--==--==--==-" or toc[16] != 3:
        raise ValueError("Unsupported IoStore TOC format")
    u32 = lambda offset: struct.unpack_from("<I", toc, offset)[0]
    header, count, blocks, block_entry = (u32(offset) for offset in (20, 24, 28, 32))
    method_count, method_width, block_size = (u32(offset) for offset in (36, 40, 44))
    if (header < 144 or count < 1 or count > 100000 or blocks > 100000
            or block_entry != 12 or method_count > 16 or method_width != 32
            or not 1 <= block_size <= 16 * 1024 * 1024 or toc[80] & 6):
        raise ValueError("Unsupported or malformed IoStore block layout")
    block_table = header + count * 22
    methods_start = block_table + blocks * block_entry
    if methods_start + method_count * method_width > len(toc):
        raise ValueError("Truncated IoStore tables")
    methods = ["None"] + [toc[methods_start+i*32:methods_start+(i+1)*32].split(b"\0")[0].decode("ascii")
                            for i in range(method_count)]
    decoded = []
    for i in range(blocks):
        record = toc[block_table+i*12:block_table+(i+1)*12]
        offset = int.from_bytes(record[:5], "little")
        compressed = int.from_bytes(record[5:8], "little")
        raw = int.from_bytes(record[8:11], "little")
        method_index = record[11]
        if not 0 < raw <= block_size or offset + compressed > len(data) or method_index >= len(methods):
            raise ValueError(f"Invalid IoStore block {i}")
        payload = data[offset:offset+compressed]
        method = methods[method_index]
        if method == "None":
            block = payload
        elif method == "Zlib":
            try:
                decoder = zlib.decompressobj()
                block = decoder.decompress(payload) + decoder.flush()
                if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                    raise ValueError("Incomplete or trailing compressed stream")
            except zlib.error as error:
                raise ValueError(f"Corrupt compressed IoStore block {i}") from error
        else:
            raise ValueError(f"Unsupported compression method {method}")
        if len(block) != raw:
            raise ValueError(f"IoStore block {i} decompressed size mismatch")
        decoded.append(block)
    chunks = {}
    for i in range(count):
        chunk_id = toc[header+i*12:header+(i+1)*12]
        record = toc[header+count*12+i*10:header+count*12+(i+1)*10]
        offset, remaining = int.from_bytes(record[:5], "big"), int.from_bytes(record[5:], "big")
        if chunk_id in chunks:
            raise ValueError("Duplicate IoStore chunk ID")
        parts = []
        while remaining:
            index, within = divmod(offset, block_size)
            if index >= len(decoded) or within >= len(decoded[index]):
                raise ValueError("Chunk references unavailable block data")
            take = min(remaining, len(decoded[index])-within)
            parts.append(decoded[index][within:within+take])
            remaining -= take
            offset += take
            if remaining and take < block_size-within:
                raise ValueError("Chunk crosses a short block")
        chunks[chunk_id] = b"".join(parts)
    return chunks


def verify_package(prefix: Path, expected_asset: Path) -> dict:
    toc = prefix.with_suffix(".utoc").read_bytes()
    chunks = unpack(toc, prefix.with_suffix(".ucas").read_bytes())
    exports = [payload for identity, payload in chunks.items() if identity[11] == 2]
    headers = [payload for identity, payload in chunks.items() if identity[11] == 10]
    if len(chunks) != 2 or len(exports) != 1 or len(headers) != 1:
        raise ValueError("Expected exactly one asset and one container-header chunk")
    if exports[0] != expected_asset.read_bytes():
        raise ValueError("Packed asset differs from the independently verified table")
    return {"blocks_verified": struct.unpack_from("<I", toc, 28)[0], "chunks_verified": len(chunks),
            "asset_sha256": hashlib.sha256(exports[0]).hexdigest(),
            "container_header_sha256": hashlib.sha256(headers[0]).hexdigest()}
