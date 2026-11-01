import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from aggregate import build
from territory_tree import build_tree
from publish_territories import publish_tree
from publish_territory_search import publish_search
from test_territory_tree import raw,ROWS,CONFIG

class TerritorialSearchTests(unittest.TestCase):
    def test_all_levels_are_searchable_without_votes_and_split_cities_keep_their_paths(self):
        payload=raw(ROWS);election=build(payload,CONFIG);tree=build_tree(payload,CONFIG,election)
        with tempfile.TemporaryDirectory()as path:
            index=publish_tree(tree,election,Path(path));directory=Path(path)/'territories'/election['id']
            ref=publish_search(directory,index);data=(directory/ref['path']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),ref['sha256'])
            document=json.loads(data);self.assertEqual(document['sourceSHA256'],election['sourceSHA256'])
            self.assertEqual({e['level']for e in document['entries']},{'Regione','Collegio','Provincia','Comune'})
            cities=[e for e in document['entries']if e['name']=='CITY']
            self.assertEqual(len(cities),2);self.assertNotEqual(cities[0]['breadcrumb'],cities[1]['breadcrumb'])
            self.assertTrue(all('votes'not in e and 'electors'not in e for e in document['entries']))
    def test_corrupt_regional_source_cannot_replace_an_index(self):
        payload=raw(ROWS);election=build(payload,CONFIG);tree=build_tree(payload,CONFIG,election)
        with tempfile.TemporaryDirectory()as path:
            index=publish_tree(tree,election,Path(path));directory=Path(path)/'territories'/election['id']
            first=publish_search(directory,index);before=(directory/first['path']).read_bytes()
            (directory/index['regions'][0]['path']).write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):publish_search(directory,index)
            self.assertEqual((directory/first['path']).read_bytes(),before)
    def test_unavailable_historical_units_remain_labeled_in_search(self):
        payload=raw(ROWS+[['PIEMONTE','U01','TORINO','EMPTY','A',0,0,0]])
        election=build(payload,CONFIG);tree=build_tree(payload,CONFIG,election)
        with tempfile.TemporaryDirectory()as path:
            index=publish_tree(tree,election,Path(path));directory=Path(path)/'territories'/election['id']
            ref=publish_search(directory,index);entries=json.loads((directory/ref['path']).read_bytes())['entries']
            self.assertIn('unavailableReason',next(e for e in entries if e['name']=='EMPTY'))
