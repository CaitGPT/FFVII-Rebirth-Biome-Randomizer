import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "tools"))
from rebirth_header import make_header,select_entry


def fixture():
    # Synthetic Rebirth-shaped metadata with two packages; the second imports
    # two package IDs. No original game header is distributed with the tests.
    row0 = struct.pack("<QiiIIII", (1<<62)|37, 1, 1, 123, 0xffffffff, 0, 0)
    row1 = struct.pack("<QiiIIII", (1<<62)|53, 1, 1, 456, 0xffffffff, 2, 8)
    imports = b"import01import02"
    blob = row0 + row1 + imports
    return (b"original" + struct.pack("<IIII",2,7,0,8) + bytes.fromhex("000064c100000000")
            + struct.pack("<I",2) + b"target01target02" + struct.pack("<I",len(blob))
            + blob + bytes(8))


class RebirthHeaderTests(unittest.TestCase):
    def test_selects_one_package_preserving_size_flags_counts_and_load_order(self):
        original = fixture()
        header,audit = make_header(original,b"target01",b"newowner",37)
        self.assertEqual(header[:8],b"newowner")
        row,imports,_ = select_entry(header,b"target01")
        old_row,_,_ = select_entry(original,b"target01")
        self.assertEqual(row,old_row)
        self.assertEqual(imports,b"")
        self.assertEqual(audit["declared_packages"],1)
        self.assertEqual(len(header),65536)
        self.assertNotIn(b"target02",header)

    def test_relocates_the_selected_packages_imports(self):
        header,_ = make_header(fixture(),b"target02",b"newowner",53)
        row,imports,_ = select_entry(header,b"target02")
        self.assertEqual(imports,b"import01import02")
        self.assertEqual(struct.unpack_from("<II",row,24),(2,8))
        self.assertNotIn(b"target01",header)

    def test_refuses_changed_asset_size_or_missing_identity(self):
        for identity,size in [(b"target01",38),(b"notfound",37)]:
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                make_header(fixture(),identity,b"newowner",size)

    def test_rejects_truncated_or_out_of_bounds_original_metadata(self):
        original = fixture()
        bad = bytearray(original)
        # Two IDs occupy bytes 36-51; entry data starts at 56.
        struct.pack_into("<I",bad,56+32+28,0xffffff00)
        for source in (original[:50],bytes(bad)):
            with self.assertRaises(ValueError):
                select_entry(source,b"target02")


if __name__ == "__main__":
    unittest.main()
