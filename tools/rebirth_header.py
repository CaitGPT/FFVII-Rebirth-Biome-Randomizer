"""Preserve the reviewed asset's actual Rebirth package-store metadata.

Rebirth's legacy container header has an extra 32-bit field before its name
batch. Generic UE4 readers used by our packager skip this layout. Only the
selected package's entry and imports are copied; no other package is declared.
"""
from __future__ import annotations
import struct


def select_entry(original: bytes, package_id: bytes) -> tuple[bytes, bytes, dict]:
    if len(package_id) != 8 or len(original) < 40:
        raise ValueError("Invalid original container header or package ID")
    count, extra, names_size, hashes_size = struct.unpack_from("<IIII", original, 8)
    if names_size != 0 or hashes_size != 8 or not 0 < count < 1000000:
        raise ValueError("Unreviewed Rebirth container name-map layout")
    if struct.unpack_from("<I", original, 32)[0] != count:
        raise ValueError("Original package counts disagree")
    ids_end = 36 + 8*count
    if ids_end + 4 > len(original):
        raise ValueError("Truncated original package IDs")
    ids = [original[36+8*i:44+8*i] for i in range(count)]
    if ids.count(package_id) != 1:
        raise ValueError("Target package ID is missing or ambiguous")
    size = struct.unpack_from("<I", original, ids_end)[0]
    start = ids_end + 4
    if size < 32*count or start + size > len(original):
        raise ValueError("Invalid original package-store data size")
    index = ids.index(package_id)
    at = start + index*32
    entry = original[at:at+32]
    imported_count, imported_offset = struct.unpack_from("<II", entry, 24)
    imported_at = at + 24 + imported_offset
    if imported_count and (imported_at < start+32*count or imported_at+8*imported_count > start+size):
        raise ValueError("Invalid original import references")
    imports = original[imported_at:imported_at+8*imported_count] if imported_count else b""
    return entry, imports, {"original_packages": count, "original_extra_field": extra,
                            "entry_index": index, "import_count": imported_count}


def make_header(original: bytes, package_id: bytes, container_id: bytes, asset_size: int) -> tuple[bytes, dict]:
    entry, imports, audit = select_entry(original, package_id)
    if len(container_id) != 8:
        raise ValueError("Container ID must be eight bytes")
    # Preserve both size flags and the original load order. This prototype only
    # changes an existing equal-sized array reference, so size changes need review.
    size_flags, exports, bundles = struct.unpack_from("<Qii", entry)
    if size_flags & ((1 << 62)-1) != asset_size or exports != 1 or bundles != 1:
        raise ValueError("Unreviewed asset size or export/bundle count")
    row = bytearray(entry)
    struct.pack_into("<I", row, 28, 8 if imports else 0)
    header = (container_id + struct.pack("<IIII", 1, 0, 0, 8) + original[24:32]
              + struct.pack("<I", 1) + package_id + struct.pack("<I", 32+len(imports))
              + row + imports + struct.pack("<II", 0, 0))
    # Shipped Rebirth headers occupy complete 64 KiB blocks, including the
    # one-package container. Raw packing places chunks consecutively: matching
    # that granularity also keeps this export's physical and TOC offsets equal.
    header += bytes((-len(header)) % 65536)
    # Independent readback checks the selected entry and its relocated imports.
    reread, reread_imports, _ = select_entry(header, package_id)
    if reread != row or reread_imports != imports:
        raise ValueError("Rebirth header metadata failed readback")
    return header, audit | {"declared_packages": 1, "header_bytes": len(header),
                           "export_count": exports, "bundle_count": bundles}
