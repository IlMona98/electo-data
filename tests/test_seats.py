import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from seats import apply_seats, parse_page, official_page

ROOT=Path(__file__).resolve().parents[1]
class SeatsTests(unittest.TestCase):
    def setUp(self):
        self.document=json.loads((ROOT/'config/seats.json').read_text())
        self.elections=[dict(id=r['electionID'],chamber=r['chamber'],territories=[dict(results=[dict(id='m5s-original',name='MOVIMENTO 5 STELLE',votes=123)])]) for r in self.document['elections']]
    def fixture(self,url):
        for r in self.document['elections']:
            for s in r['sources']:
                if s['url']==url:return (ROOT/'tests/fixtures/seats'/f"{r['electionID']}-{s['kind']}.html").read_bytes()
        raise ValueError('Unexpected source')
    def test_real_ministerial_tables_reconcile_entire_chambers_and_reuse_bindings(self):
        result=apply_seats(self.elections,self.document,self.fixture)
        for e in result:
            s=e['seats']
            self.assertEqual(sum(g['seats'] for g in s['groups'])+s['unassignedSeats'],s['totalSeats'])
            self.assertEqual(next(g for g in s['groups'] if g['name']=='MOVIMENTO 5 STELLE')['resultID'],'m5s-original')
            self.assertEqual(e['territories'][0]['results'][0]['votes'],123)
            self.assertEqual(s['sourceLabel'],'Eligendo · Archivio')
            self.assertEqual(len(s['sourcePages']),3)
        self.assertEqual(next(e['seats'] for e in result if e['id']=='senato-2018')['unassignedSeats'],1)
        camera=next(e['seats'] for e in result if e['id']=='camera-2022')
        self.assertEqual(next(g['seats'] for g in camera['groups'] if g['id']=='seats-centrodestra'),237)
        self.assertEqual(next(g['seats'] for g in camera['groups'] if g['id']=='seats-centrosinistra'),84)
    def test_italia_excludes_valle_daosta_and_estero(self):
        r=self.document['elections'][0];s=r['sources'][0]
        self.assertEqual(sum(b['seats'] for b in parse_page(self.fixture(s['url']),s)),617)
        self.assertNotEqual(617,r['totalSeats'])
    def test_valle_daosta_uses_elected_marker_not_largest_vote_count(self):
        s=self.document['elections'][0]['sources'][2];raw=self.fixture(s['url'])
        self.assertEqual(parse_page(raw,s),[dict(seats=1,lists=['MOVIMENTO 5 STELLE'])])
        with self.assertRaises(ValueError):parse_page(raw.replace(b'Eletto',b''),s)
    def test_changed_totals_or_duplicate_rows_stop_publication(self):
        s=self.document['elections'][0]['sources'][0];raw=self.fixture(s['url'])
        for corrupted in [raw.replace(b'>111<',b'>112<',1),raw.replace(b'id="lista0_1"',b'id="lista0_0"'),raw.replace(b'headers="hlista candidato0"',b'headers="hlista candidato1"',1)]:
            with self.assertRaises(ValueError):parse_page(corrupted,s)
    def test_block_pages_wrong_year_and_missing_seat_column_are_rejected(self):
        s=self.document['elections'][0]['sources'][0];raw=self.fixture(s['url'])
        for corrupted in [b'<html>Access denied</html>',raw.replace(b'04/03/2018',b'25/09/2022'),raw.replace(b'id="hseggi"',b'id="other"')]:
            with self.assertRaises(ValueError):parse_page(corrupted,s)
    def test_missing_area_and_ambiguous_coalition_are_rejected(self):
        for mutation in ['area','coalition','capacity','chamber','url']:
            d=copy.deepcopy(self.document);r=d['elections'][0]
            if mutation=='area':r['sources'].pop()
            elif mutation=='coalition':r['groups'][0]['aliases'].append('LEGA')
            elif mutation=='capacity':r['totalSeats']-=1
            elif mutation=='chamber':r['chamber']='senato'
            else:r['sources'][0]['url']=r['sources'][0]['url'].replace('tpel=C','tpel=S')
            with self.assertRaises(ValueError):apply_seats(self.elections,d,self.fixture)
    def test_upstream_failure_keeps_all_previous_allocations_untouched(self):
        for e in self.elections:e['seats']={'lastGood':True}
        before=copy.deepcopy(self.elections)
        def fail_after_first_election(url):
            if 'tpel=S' in url:raise OSError('upstream unavailable')
            return self.fixture(url)
        with self.assertRaises(OSError):apply_seats(self.elections,self.document,fail_after_first_election)
        self.assertEqual(self.elections,before)
    def test_nonministerial_redirect_and_unknown_election_are_rejected(self):
        for url in ['https://example.com/index.php','https://elezionistorico.interno.gov.it@evil.com/index.php','https://elezionistorico.interno.gov.it/info.php']:
            with self.assertRaises(ValueError):official_page(url)
        self.document['elections'][0]['electionID']='camera-2030'
        with self.assertRaises(ValueError):apply_seats(self.elections,self.document,self.fixture)
