"""Synthetic container-contract checks; these do not pass native game cases."""
import struct,sys,tempfile,unittest,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from rebirth_container import write_override
from container_check import unpack
from test_container_check import fixture


class SyntheticCodec:
    # Deliberately a fake codec for layout testing, never packaged for the game.
    def compress(self,payload): return zlib.compress(payload)
    def decompress(self,payload,size): return zlib.decompress(payload)


class WriterTests(unittest.TestCase):
    def setUp(self):
        scratch=ROOT/'build'/'test-temp'
        scratch.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=scratch)
        self.folder=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.asset=self.folder/'synthetic.uasset'
        self.asset.write_bytes(b'synthetic reviewed export payload')
        toc,_,_=fixture()
        self.toc=bytearray(toc)
        self.toc[56:64]=b'owner123'
        self.toc[144:156]=b'owner123'+bytes(3)+bytes([10])

    def test_preserves_export_with_empty_legacy_header_and_compressed_metadata(self):
        prefix=self.folder/'Test_P'
        receipt=write_override(prefix,bytes(self.toc),self.asset,SyntheticCodec())
        toc=prefix.with_suffix('.utoc').read_bytes()
        chunks=unpack(toc,prefix.with_suffix('.ucas').read_bytes(),oodle_decoder=SyntheticCodec().decompress)
        header=next(p for cid,p in chunks.items() if cid[11]==10)
        export=next(p for cid,p in chunks.items() if cid[11]==2)
        self.assertEqual(export,self.asset.read_bytes())
        self.assertEqual(len(header),65536)
        self.assertEqual(struct.unpack_from('<IIII',header,8),(0,0,0,8))
        self.assertEqual(header[:8],toc[56:64])
        self.assertEqual(toc[-1],1)
        self.assertEqual(toc[-34],0)
        self.assertEqual(receipt['chunks_verified'],2)

    def test_refuses_container_identity_mismatch_before_writing(self):
        self.toc[56:64]=bytes(8)
        with self.assertRaisesRegex(ValueError,'IDs disagree'):
            write_override(self.folder/'Test_P',bytes(self.toc),self.asset,SyntheticCodec())
        self.assertFalse((self.folder/'Test_P.ucas').exists())

    def test_two_exports_keep_their_identity_and_bytes(self):
        toc=bytearray(self.toc[:144])
        struct.pack_into('<I',toc,24,3)
        struct.pack_into('<I',toc,28,3)
        extra=b'second12345'+bytes([2])
        toc+=self.toc[144:168]+extra+bytes(30+36+32+99)
        other=self.folder/'second.uasset'
        other.write_bytes(b'another synthetic reviewed export')
        wanted={bytes(self.toc[156:168]):self.asset,extra:other}
        prefix=self.folder/'Two_P'
        receipt=write_override(prefix,bytes(toc),wanted,SyntheticCodec())
        chunks=unpack(prefix.with_suffix('.utoc').read_bytes(),prefix.with_suffix('.ucas').read_bytes(),oodle_decoder=SyntheticCodec().decompress)
        self.assertEqual({cid:p for cid,p in chunks.items() if cid[11]==2},{cid:p.read_bytes() for cid,p in wanted.items()})
        self.assertEqual(receipt['chunks_verified'],3)

    def test_refuses_a_bad_compressor_before_writing(self):
        class BadCodec(SyntheticCodec):
            def compress(self,payload): return zlib.compress(b'wrong payload')
        with self.assertRaisesRegex(ValueError,'size mismatch'):
            write_override(self.folder/'Test_P',bytes(self.toc),self.asset,BadCodec())
        self.assertFalse((self.folder/'Test_P.ucas').exists())
