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
from identities import render_svg
from PIL import Image
from defusedxml.common import DefusedXmlException
from xml.etree.ElementTree import ParseError
import io

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
        for path in ['../logo.png','symbols/../logo.png','https://example.org/logo.png','symbols/logo.gif']:
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
    def test_svg_is_rendered_and_registry_remains_ios_compatible(self):
        with tempfile.TemporaryDirectory() as folder:
            public=Path(folder);(public/'symbols').mkdir()
            svg=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><rect width="100" height="50" fill="#123456"/></svg>'
            (public/'symbols/example.svg').write_bytes(svg)
            value=entity();value['symbolPath']='symbols/example.svg'
            record=compile_registry(registry(value),public)['entities'][0]
            self.assertTrue(record['symbolPath'].endswith('.png'))
            raw=(public/record['symbolPath']).read_bytes()
            self.assertEqual(record['symbolSHA256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual((public/'symbols/example.svg').read_bytes(),svg)
            image=Image.open(io.BytesIO(raw)).convert('RGBA')
            self.assertEqual(image.size,(512,512))
            self.assertEqual(image.getpixel((256,256)),(18,52,86,255))
            self.assertEqual(image.getpixel((256,0))[3],0)
            self.assertEqual(compile_registry(registry(value),public)['entities'][0],record)
            (public/'symbols/example.svg').write_bytes(svg.replace(b'#123456',b'#ffffff'))
            self.assertNotEqual(compile_registry(registry(value),public)['entities'][0]['symbolPath'],record['symbolPath'])
            self.assertTrue((public/record['symbolPath']).exists())
    def test_svg_internal_gradients_and_references_are_rendered(self):
        raw=render_svg(b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><defs>
            <linearGradient id="g"><stop stop-color="red"/><stop offset="1" stop-color="blue"/></linearGradient>
            <rect id="r" width="10" height="10" fill="url(#g)"/></defs><use href="#r"/></svg>''')
        image=Image.open(io.BytesIO(raw)).convert('RGBA')
        self.assertEqual(image.getpixel((256,256))[3],255)
        self.assertNotEqual(image.getpixel((10,256)),image.getpixel((500,256)))
    def test_svg_external_resources_and_active_content_are_rejected(self):
        examples=[
            '<html/>', '<svg><script>bad()</script></svg>',
            '<svg onload="bad()"/>', '<svg><foreignObject/></svg>',
            '<svg><image href="file:///etc/passwd"/></svg>',
            '<svg><use href="https://example.org/logo.svg#shape"/></svg>',
            '<svg><style>@import url(https://example.org/style.css);</style></svg>',
            '<svg><rect width="10" height="10" fill="url(file:///etc/passwd)"/></svg>',
            '<!DOCTYPE svg [<!ENTITY x "bad">]><svg>&x;</svg>', '<svg>',
        ]
        for svg in examples:
            with self.subTest(svg=svg):
                with self.assertRaises((ValueError,ParseError,DefusedXmlException)):render_svg(svg.encode())
    def test_oversized_svg_is_rejected(self):
        with self.assertRaises(ValueError):render_svg(b' '*2_000_001)
    def test_source_names_and_bindings_catalog_is_deduplicated(self):
        row=dict(id='same',name='Exact source name',votes=1)
        elections=[dict(id='camera-2018',territories=[dict(results=[row]),dict(results=[row])]),dict(id='senato-2018',territories=[dict(results=[row])])]
        entries=candidate_catalog(elections)['candidates']
        self.assertEqual(len(entries),1)
        self.assertEqual(len(entries[0]['bindings']),2)
if __name__=='__main__':unittest.main()

class IdentityLinkTests(unittest.TestCase):
    def test_position_is_preserved_and_invalid_positions_are_rejected(self):
        value=entity();value['hemicycleOrder']=25
        self.assertEqual(compile_registry(registry(value),Path('.'))['entities'][0]['hemicycleOrder'],25)
        for invalid in [-1,101,True,2.5,'left',None]:
            value['hemicycleOrder']=invalid
            with self.assertRaises(ValueError):compile_registry(registry(value),Path('.'))
    def test_canonical_links_use_binding_before_alias_and_keep_electoral_ids(self):
        from identities import apply_identity_links
        party=entity('m5s');party['aliases']=['Old ballot','New ballot']
        coalition=entity('left');coalition.update(kind='coalition',aliases=['Centrosinistra'])
        bound=entity('special');bound.update(aliases=[],bindings=[dict(electionID='new',resultID='other')])
        elections=[dict(id='old',territories=[dict(results=[dict(id='a',name='Old ballot')])]),dict(id='new',seats=dict(groups=[dict(id='local-group',name='Centrosinistra',seats=10)]),territories=[dict(results=[dict(id='b',name='New ballot',coalitionID='local-group',coalitionName='Original coalition'),dict(id='other',name='New ballot'),dict(id='unknown',name='Unconfigured')])])]
        apply_identity_links(elections,compile_registry(registry(party,coalition,bound),Path('.')))
        rows=elections[1]['territories'][0]['results']
        self.assertEqual(elections[0]['territories'][0]['results'][0]['entityID'],rows[0]['entityID'])
        self.assertEqual(rows[0]['coalitionEntityID'],'left')
        self.assertEqual(rows[0]['coalitionID'],'local-group')
        self.assertEqual(rows[1]['entityID'],'special')
        self.assertNotIn('entityID',rows[2])
        self.assertEqual(elections[1]['seats']['groups'][0]['entityID'],'left')
