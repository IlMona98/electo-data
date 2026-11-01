import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from aggregate import build
from territory_tree import build_tree,region_name
from publish_territories import publish_tree
CONFIG=dict(id='camera-test',columns=['REGIONE','COMUNE','LISTA','VOTI','ELETTORI','VOTANTI'],unit=['REGIONE','COLLEGIO','PROVINCIA','COMUNE'],level='Regione',note='source')
HEADER=['REGIONE','COLLEGIO','PROVINCIA','COMUNE','LISTA','VOTI','ELETTORI','VOTANTI']
ROWS=[['PIEMONTE','U01','TORINO','CITY','A',30,100,70],['PIEMONTE','U01','TORINO','CITY','B',20,100,70],['PIEMONTE','U02','TORINO','CITY','A',5,40,20],['PIEMONTE','U02','TORINO','CITY','B',10,40,20],['LOMBARDIA 1','U03','MILANO','OTHER','A',8,30,15]]
def raw(rows):
    s=io.StringIO();w=csv.writer(s,delimiter=';');w.writerow(HEADER);w.writerows(rows);return s.getvalue().encode()
class TerritorialTreeTests(unittest.TestCase):
    def test_split_municipality_remains_scoped_and_does_not_duplicate_turnout(self):
        data=raw(ROWS);verified=build(data,CONFIG);tree=build_tree(data,CONFIG,verified)
        self.assertEqual(len([n for n in tree['nodes']if n['parentID']=='italia']),2)
        cities=[n for n in tree['nodes']if n['level']=='Comune'and n['name']=='CITY']
        self.assertEqual(len(cities),2);self.assertNotEqual(cities[0]['id'],cities[1]['id'])
        self.assertEqual(sum(c['electors']for c in cities),140)
        self.assertTrue(all('collegio'in c['scopeNote']for c in cities))
        self.assertIn('Provincia',tree['levels'])
    def test_wrong_national_totals_and_conflicting_ballots_cannot_publish(self):
        data=raw(ROWS);v=build(data,CONFIG);v['territories'][0]['voters']+=1
        with self.assertRaises(ValueError):build_tree(data,CONFIG,v)
        v=build(data,CONFIG);v['territories'][0]['results'][0]['votes']+=1
        with self.assertRaises(ValueError):build_tree(data,CONFIG,v)
        with self.assertRaises(ValueError):build_tree(raw(ROWS+[ROWS[0]]),CONFIG,build(data,CONFIG))
    def test_regional_documents_are_immutable_and_hash_checked(self):
        data=raw(ROWS);v=build(data,CONFIG)|dict(sourceSHA256=hashlib.sha256(data).hexdigest())
        tree=build_tree(data,CONFIG,v)
        with tempfile.TemporaryDirectory()as path:
            index=publish_tree(tree,v,Path(path))
            for region in index['regions']:
                p=Path(path)/'territories'/v['id']/region['path'];payload=p.read_bytes()
                self.assertEqual(hashlib.sha256(payload).hexdigest(),region['sha256'])
                self.assertEqual(json.loads(payload)['sourceSHA256'],v['sourceSHA256'])
    def test_regions_merge_only_known_numbered_constituencies(self):
        self.assertEqual(region_name('LOMBARDIA 1'),'LOMBARDIA')
        self.assertEqual(region_name('LOMBARDIA 2'),'LOMBARDIA')
        self.assertEqual(region_name('Emilia-Romagna'),'EMILIA ROMAGNA')
        self.assertEqual(region_name('Torino-Novara-Vercelli'),'Torino-Novara-Vercelli')
    def test_missing_province_is_skipped_instead_of_invented(self):
        data=raw(ROWS).decode().splitlines();data=[line.replace(';PROVINCIA','').replace(';TORINO','').replace(';MILANO','')for line in data]
        config=copy.deepcopy(CONFIG);config['unit'].remove('PROVINCIA');payload=('\n'.join(data)+'\n').encode()
        tree=build_tree(payload,config,build(payload,config));self.assertNotIn('Provincia',tree['levels'])
