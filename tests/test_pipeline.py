import copy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from aggregate import build
from sync import official_url, publish

CONFIG=dict(id='fixture',title='Example',category='europee',year=2024,dateLabel='Example',coverage='Test',note='Test scope',sourceURL='https://elezionistorico.interno.gov.it/daithome/documenti/opendata/test.csv',sourceFile='test.csv',columns=['REGIONE','COMUNE','LISTA','VOTI','ELETTORI','VOTANTI'],unit=['REGIONE','COMUNE'],level='Regione')
ROWS=[['North','One','A','30','100','60'],['North','One','B','20','100','60'],['South','Two','A','10','50','30'],['South','Two','B','15','50','30']]
def data(rows):
    stream=io.StringIO();writer=csv.writer(stream,delimiter=';');writer.writerow(['REGIONE','COMUNE','LISTA','VOTI','ELETTORI','VOTANTI']);writer.writerows(rows);return stream.getvalue().encode()
class PipelineTests(unittest.TestCase):
    def test_electors_are_not_counted_for_each_list(self):
        result=build(data(ROWS),CONFIG)
        self.assertEqual(result['territories'][0]['electors'],150)
        self.assertEqual(result['territories'][0]['voters'],90)
        self.assertEqual(result['sourceUnits'],2)
        self.assertEqual(sum(r['votes'] for r in result['territories'][0]['results']),75)
    def test_rejects_duplicate_ballot_rows(self):
        with self.assertRaises(ValueError):build(data(ROWS+[ROWS[0]]),CONFIG)
    def test_rejects_conflicting_turnout(self):
        rows=copy.deepcopy(ROWS);rows[1][-1]='59'
        with self.assertRaises(ValueError):build(data(rows),CONFIG)
    def test_rejects_negative_or_impossible_votes(self):
        rows=copy.deepcopy(ROWS);rows[0][3]='-1'
        with self.assertRaises(ValueError):build(data(rows),CONFIG)
        rows[0][3]='500'
        with self.assertRaises(ValueError):build(data(rows),CONFIG)
    def test_does_not_publish_download_configuration(self):
        result=build(data(ROWS),CONFIG|dict(downloadURL='internal',zipMember='member.txt'))
        self.assertNotIn('columns',result);self.assertNotIn('downloadURL',result);self.assertNotIn('zipMember',result)
    def test_allows_only_official_https_sources(self):
        official_url(CONFIG['sourceURL'])
        for url in ['http://elezionistorico.interno.gov.it/daithome/documenti/opendata/x', 'https://example.com/a', 'https://elezionistorico.interno.gov.it.evil.test/daithome/documenti/opendata/a', 'https://elezionistorico.interno.gov.it/not-allowed']:
            with self.assertRaises(ValueError):official_url(url)
    def test_catalog_points_to_hash_checked_immutable_document(self):
        election=build(data(ROWS),CONFIG)|dict(retrievedAt='2026-10-28T10:00:00Z',checkedAt='2026-10-28T11:00:00Z')
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder);publish([election],directory)
            catalog=json.loads((directory/'catalog.json').read_text())
            entry=catalog['elections'][0]
            import hashlib
            payload=(directory/entry['path']).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(),entry['sha256'])
            self.assertEqual(json.loads(payload)['elections'][0]['territories'][0]['voters'],90)
            self.assertEqual(json.loads((directory/'archive.json').read_text())['elections'][0]['id'],'fixture')
    def test_rejects_html_and_empty_csv(self):
        for raw in [b'',b'<html>Access denied</html>']:
            with self.assertRaises((ValueError,KeyError)):build(raw,CONFIG)
if __name__=='__main__':unittest.main()
