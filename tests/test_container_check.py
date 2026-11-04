import struct
import sys
from pathlib import Path
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from container_check import unpack, legacy_toc, verify_legacy_metadata


def fixture(compressed=True):
    # Synthetic two-chunk TOC; these are not original game bytes.
    payloads = [b"synthetic metadata", b"synthetic asset data"]
    toc = bytearray(144)
    toc[:16] = b"-==--==--==--==-"
    toc[16] = 3
    for offset, value in [(20,144),(24,2),(28,2),(32,12),(36,1),(40,32),(44,64)]:
        struct.pack_into("<I", toc, offset, value)
    toc[80] = 9
    ids = [b"header12345" + bytes([10]), b"export12345" + bytes([2])]
    toc.extend(b"".join(ids))
    for i, payload in enumerate(payloads):
        toc.extend((i*64).to_bytes(5,"big") + len(payload).to_bytes(5,"big"))
    data = bytearray()
    for payload in payloads:
        packed = zlib.compress(payload) if compressed else payload
        toc.extend(len(data).to_bytes(5,"little") + len(packed).to_bytes(3,"little")
                   + len(payload).to_bytes(3,"little") + bytes([int(compressed)]))
        data.extend(packed)
    toc.extend(b"Zlib" + bytes(28))
    toc.extend(bytes(66))
    return bytes(toc), bytes(data), dict(zip(ids,payloads))


class ContainerTests(unittest.TestCase):
    def test_reads_both_compressed_chunks_and_uncompressed_chunks(self):
        for compressed in (True,False):
            toc,data,wanted = fixture(compressed)
            self.assertEqual(unpack(toc,data),wanted)

    def test_rejects_overwritten_compressed_header_regression(self):
        toc,data,_ = fixture()
        broken = bytes.fromhex("8c060097a68897a4d300") + data[10:]
        with self.assertRaisesRegex(ValueError,"Corrupt compressed IoStore block 0"):
            unpack(toc,broken)

    def test_rejects_truncated_data_and_unknown_format(self):
        toc,data,_ = fixture()
        for bad_toc,bad_data in [(toc,data[:-1]),(bytes(16)+toc[16:],data),(toc[:200],data)]:
            with self.subTest(length=len(bad_toc)), self.assertRaises(ValueError):
                unpack(bad_toc,bad_data)

    def test_rejects_duplicate_chunk_ids_from_installed_override(self):
        toc,data,_ = fixture()
        broken = bytearray(toc)
        broken[156:168] = broken[144:156]
        with self.assertRaisesRegex(ValueError,"Duplicate IoStore chunk ID"):
            unpack(bytes(broken),data)

    def test_legacy_conversion_preserves_every_payload_and_verifies_hashes(self):
        toc,data,wanted = fixture()
        converted = legacy_toc(toc,data)
        self.assertEqual(unpack(converted,data),wanted)
        self.assertEqual(converted[16],2)
        verify_legacy_metadata(converted,wanted)
        broken = bytearray(converted)
        broken[-66] ^= 1
        with self.assertRaisesRegex(ValueError,"SHA-1 metadata mismatch"):
            verify_legacy_metadata(bytes(broken),wanted)

    def test_legacy_conversion_refuses_an_unreviewed_metadata_tail(self):
        toc,data,_ = fixture()
        with self.assertRaisesRegex(ValueError,"metadata layout"):
            legacy_toc(toc+b"unexpected",data)

    def test_legacy_chunk_flags_match_compressed_and_raw_blocks(self):
        for compressed in (True,False):
            toc,data,wanted = fixture(compressed)
            converted = legacy_toc(toc,data)
            self.assertEqual(converted[-1],int(compressed))
            self.assertEqual(converted[-34],int(compressed))
            verify_legacy_metadata(converted,wanted)


if __name__ == "__main__":
    unittest.main()
