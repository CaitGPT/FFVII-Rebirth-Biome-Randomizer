"""Write the small Rebirth override layout exercised by native controls."""
from __future__ import annotations
from pathlib import Path
import struct
from container_check import unpack,verify_package


def write_override(prefix: Path, template_toc: bytes, asset: Path | dict[bytes,Path], codec) -> dict:
    u32 = lambda at: struct.unpack_from("<I",template_toc,at)[0]
    header_size,count = u32(20),u32(24)
    identities = [template_toc[header_size+12*i:header_size+12*(i+1)] for i in range(count)]
    if not 2 <= count <= 10 or [cid[11] for cid in identities] != [10]+[2]*(count-1):
        raise ValueError("Expected reviewed header-first export archive")
    container_id = template_toc[56:64]
    if identities[0] != container_id+bytes(3)+bytes([10]):
        raise ValueError("Header chunk and container IDs disagree")
    assets = asset if isinstance(asset,dict) else {identities[1]:asset}
    if set(assets) != set(identities[1:]):
        raise ValueError("Expected exact reviewed export identities")
    payloads = {cid:path.read_bytes() for cid,path in assets.items()}
    if any(not 0 < len(payload) <= 65536 for payload in payloads.values()):
        raise ValueError("Unreviewed asset block count")
    # Existing assets use their original game package-store metadata. The
    # generic packager's malformed legacy header is replaced, never patched
    # through an arbitrary compressed byte prefix.
    header = container_id+struct.pack("<IIII",0,0,0,8)+struct.pack("<Q",0xc1640000)+bytes(16)
    header += bytes(65536-len(header))
    payloads[identities[0]] = header
    data,offsets,blocks = bytearray(),bytearray(),bytearray()
    for i,cid in enumerate(identities):
        payload = payloads[cid]
        method = int(cid[11] == 2)
        encoded = codec.compress(payload) if method else payload
        offsets += (i*65536).to_bytes(5,"big")+len(payload).to_bytes(5,"big")
        blocks += len(data).to_bytes(5,"little")+len(encoded).to_bytes(3,"little")+len(payload).to_bytes(3,"little")+bytes([method])
        data += encoded+bytes((-len(encoded))%16)
    directory_at = header_size+count*22+u32(28)*12+u32(36)*u32(40)
    directory = template_toc[directory_at:directory_at+u32(48)]
    head = bytearray(144)
    head[:16] = b"-==--==--==--==-"
    head[16] = 2
    for at,value in [(20,144),(24,count),(28,count),(32,12),(36,1),(40,32),(44,65536),(48,len(directory))]:
        struct.pack_into("<I",head,at,value)
    head[56:64] = container_id
    head[80] = 9
    data = bytes(data)
    toc = bytes(head)+b"".join(identities)+offsets+blocks+b"Oodle"+bytes(27)+directory+bytes(33*count)
    from container_check import legacy_toc
    toc = legacy_toc(toc,data,oodle_decoder=codec.decompress)
    decoded = unpack(toc,data,oodle_decoder=codec.decompress)
    if decoded != payloads:
        raise ValueError("Native override failed independent chunk readback")
    prefix.with_suffix(".utoc").write_bytes(toc)
    prefix.with_suffix(".ucas").write_bytes(data)
    return verify_package(prefix,assets,oodle_decoder=codec.decompress)
