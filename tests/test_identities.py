import copy
import hashlib
import struct
import zlib
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from identities import compile_registry, candidate_catalog

def entity(identity='example'):
    return dict(id=identity,label='Example',shortLabel='EX',kind='party',colorHex='123456',aliases=['Partito esempio'],bindings=[])
def registry(*entities):return dict(schemaVersion=1,entities=list(entities))
def png(width=1,height=1):
    def chunk(tag,raw):return struct.pack('>I',len(raw))+tag+raw+struct.pack('>I',zlib.crc32(tag+raw)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\xff\0\0\xff'))+chunk(b'IEND',b'')
class IdentityTests(unittest.TestCase):
    def test_empty_registry_is_neutral(self):
        self.assertEqual(compile_registry(registry(),Path('.'))['entities'],[])
    def test_invalid_color_is_rejected(self):
        value=entity();value['colorHex']='#123456'
        with self.assertRaises(ValueError):compile_registry(registry(value),Path('.'))
    def test_normalized_alias_collision_is_rejected(self):
        other=entity('other');other['aliases']=[' PÀRTITO  ESEMPIO ']
        with self.assertRaises(ValueError):compile_registry(registry(entity(),other),Path('.'))
    def test_duplicate_binding_is_rejected(self):
        one=entity();two=entity('other');two['aliases']=[]
        one['bindings']=two['bindings']=[dict(electionID='camera-2018',resultID='a')]
        with self.assertRaises(ValueError):compile_registry(registry(one,two),Path('.'))
    def test_binding_can_differ_by_chamber(self):
        one=entity();two=entity('other');two['aliases']=[]
        one['bindings']=[dict(electionID='camera-2018',resultID='a')];two['bindings']=[dict(electionID='senato-2018',resultID='a')]
        self.assertEqual(len(compile_registry(registry(one,two),Path('.'))['entities']),2)
    def test_external_and_traversing_symbols_are_rejected(self):
        for path in ['../logo.png','symbols/../logo.png','https://example.org/logo.png','symbols/logo.svg']:
            value=entity();value['symbolPath']=path
            with self.assertRaises(ValueError):compile_registry(registry(value),Path('.'))
    def test_symbol_hash_is_computed_from_repo_asset(self):
        with tempfile.TemporaryDirectory() as folder:
            public=Path(folder);(public/'symbols').mkdir()
            raw=png()
            (public/'symbols/example.png').write_bytes(raw)
            value=entity();value['symbolPath']='symbols/example.png'
            result=compile_registry(registry(value),public)
            self.assertEqual(result['entities'][0]['symbolSHA256'],hashlib.sha256(raw).hexdigest())
    def test_invalid_symbol_dimensions_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            public=Path(folder);(public/'symbols').mkdir()
            raw=png(99999,1)
            (public/'symbols/example.png').write_bytes(raw)
            value=entity();value['symbolPath']='symbols/example.png'
            with self.assertRaises(ValueError):compile_registry(registry(value),public)
    def test_source_names_and_bindings_catalog_is_deduplicated(self):
        row=dict(id='same',name='Exact source name',votes=1)
        elections=[dict(id='camera-2018',territories=[dict(results=[row]),dict(results=[row])]),dict(id='senato-2018',territories=[dict(results=[row])])]
        entries=candidate_catalog(elections)['candidates']
        self.assertEqual(len(entries),1)
        self.assertEqual(len(entries[0]['bindings']),2)
if __name__=='__main__':unittest.main()
