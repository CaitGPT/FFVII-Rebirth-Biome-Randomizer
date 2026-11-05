"""Use the owner's installed Oodle library; no proprietary DLL is distributed."""
from __future__ import annotations
import ctypes
from pathlib import Path


class OodleCodec:
    def __init__(self, path: Path):
        self.path = Path(path).resolve(strict=True)
        self.library = ctypes.CDLL(str(self.path))
        self.decode = self.library.OodleLZ_Decompress
        self.decode.restype = ctypes.c_int64
        self.decode.argtypes = [ctypes.c_char_p,ctypes.c_int64,ctypes.c_char_p,ctypes.c_int64,
                               ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_int64,
                               ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int64,ctypes.c_int]
        self.encode = self.library.OodleLZ_Compress
        self.encode.restype = ctypes.c_int64
        self.encode.argtypes = [ctypes.c_int,ctypes.c_char_p,ctypes.c_int64,ctypes.c_char_p,ctypes.c_int,
                               ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int64]

    def decompress(self, payload: bytes, size: int) -> bytes:
        if not 0 < size <= 65536:
            raise ValueError("Unreviewed Oodle block size")
        output = ctypes.create_string_buffer(size)
        actual = self.decode(payload,len(payload),output,size,1,1,0,None,0,None,None,None,0,3)
        if actual != size:
            raise ValueError(f"Oodle decompression size mismatch: {actual}, expected {size}")
        return output.raw[:size]

    def compress(self, payload: bytes) -> bytes:
        if not 0 < len(payload) <= 65536:
            raise ValueError("Unreviewed Oodle block size")
        output = ctypes.create_string_buffer(len(payload)+len(payload)//16+512)
        # Kraken, normal compression level. Verification is mandatory even
        # when the library returns a positive compressed length.
        actual = self.encode(8,payload,len(payload),output,4,None,None,None,None,0)
        if not 0 < actual <= len(output):
            raise ValueError("Oodle compression failed")
        encoded = output.raw[:actual]
        if self.decompress(encoded,len(payload)) != payload:
            raise ValueError("Oodle compressed block failed exact round-trip")
        return encoded
