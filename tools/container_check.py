"""Independent checks for this mod's UE4 directory-index IoStore packages.

Reads and decompresses every block, then reconstructs each chunk using the TOC.
This supports unencrypted, unsigned v2 and v3 directory-index packages.
It does not certify the game's package dependency or spawn behavior.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import struct
import zlib


def unpack(toc: bytes, data: bytes, *, oodle_decoder=None) -> dict[bytes, bytes]:
    if len(toc) < 144 or toc[:16] != b"-==--==--==--==-" or toc[16] not in (2, 3):
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
        elif method == "Oodle" and callable(oodle_decoder):
            block = oodle_decoder(payload,raw)
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


def legacy_meta_row(toc: bytes, index: int, payload: bytes) -> bytes:
    u32 = lambda offset: struct.unpack_from("<I", toc, offset)[0]
    block_size = u32(44)
    record = u32(20) + u32(24)*12 + index*10
    offset = int.from_bytes(toc[record:record+5], "big")
    start = offset // block_size
    end = (offset + len(payload) + block_size - 1) // block_size
    block_table = u32(20) + u32(24)*22
    compressed = any(toc[block_table+i*12+11] != 0 for i in range(start,end))
    return hashlib.sha1(payload).digest() + bytes(12) + bytes([int(compressed)])


def legacy_toc(toc: bytes, data: bytes, *, oodle_decoder=None) -> bytes:
    """Keep all blocks/IDs/paths; use UE4's v2 header fields and SHA-1 metas."""
    chunks = unpack(toc, data,oodle_decoder=oodle_decoder)
    u32 = lambda offset: struct.unpack_from("<I", toc, offset)[0]
    count = u32(24)
    meta_start = u32(20) + count*22 + u32(28)*12 + u32(36)*u32(40) + u32(48)
    if meta_start + 33*count != len(toc):
        raise ValueError("Unreviewed IoStore metadata layout")
    result = bytearray(toc)
    result[16] = 2
    result[84:144] = bytes(60)
    for i in range(count):
        cid = toc[u32(20)+i*12:u32(20)+(i+1)*12]
        result[meta_start+i*33:meta_start+(i+1)*33] = legacy_meta_row(toc,i,chunks[cid])
    verify_legacy_metadata(bytes(result), chunks)
    return bytes(result)


def verify_legacy_metadata(toc: bytes, chunks: dict[bytes, bytes]) -> None:
    if toc[16] != 2 or any(toc[84:144]):
        raise ValueError("Expected native legacy TOC fields")
    u32 = lambda offset: struct.unpack_from("<I", toc, offset)[0]
    count = u32(24)
    at = u32(20) + count*22 + u32(28)*12 + u32(36)*u32(40) + u32(48)
    if at + 33*count != len(toc):
        raise ValueError("Invalid legacy chunk metadata size")
    for i in range(count):
        cid = toc[u32(20)+i*12:u32(20)+(i+1)*12]
        expected = legacy_meta_row(toc,i,chunks[cid])
        if toc[at+i*33:at+(i+1)*33] != expected:
            raise ValueError("Legacy chunk SHA-1 metadata mismatch")


def verify_package(prefix: Path, expected_asset: Path | dict[bytes,Path], *, oodle_decoder=None) -> dict:
    toc = prefix.with_suffix(".utoc").read_bytes()
    chunks = unpack(toc, prefix.with_suffix(".ucas").read_bytes(),oodle_decoder=oodle_decoder)
    if toc[16] == 2:
        verify_legacy_metadata(toc, chunks)
    exports = {identity:payload for identity,payload in chunks.items() if identity[11] == 2}
    headers = [payload for identity, payload in chunks.items() if identity[11] == 10]
    wanted = expected_asset if isinstance(expected_asset,dict) else {next(iter(exports)):expected_asset}
    if len(chunks) != len(wanted)+1 or exports.keys() != wanted.keys() or len(headers) != 1:
        raise ValueError("Expected exactly the reviewed assets and one container-header chunk")
    if any(exports[cid] != path.read_bytes() for cid,path in wanted.items()):
        raise ValueError("Packed asset differs from the independently verified table")
    return {"blocks_verified": struct.unpack_from("<I", toc, 28)[0], "chunks_verified": len(chunks),
            "asset_sha256": hashlib.sha256(next(iter(exports.values()))).hexdigest() if len(exports)==1 else None,
            "asset_hashes": {cid.hex():hashlib.sha256(payload).hexdigest() for cid,payload in exports.items()},
            "container_header_sha256": hashlib.sha256(headers[0]).hexdigest()}
