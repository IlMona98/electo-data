import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from seats import apply_seats, parse_page, official_page
from urllib.parse import parse_qs,urlsplit

ROOT=Path(__file__).resolve().parents[1]
class SeatsTests(unittest.TestCase):
    def setUp(self):
        self.document=json.loads((ROOT/'config/seats.json').read_text())
        self.document['elections']=[r for r in self.document['elections'] if r.get('adapter')!='historical-pages']
        self.elections=[dict(id=r['electionID'],chamber=r['chamber'],territories=[dict(results=[dict(id='m5s-original',name='MOVIMENTO 5 STELLE',votes=123)])]) for r in self.document['elections']]
    def fixture(self,url):
        for r in self.document['elections']:
            for s in r['sources']:
                if s['url']==url:
                    suffix=s['kind']+('-'+parse_qs(urlsplit(url).query)['ne1'][0] if s['kind']=='uninominale' else '')
                    return (ROOT/'tests/fixtures/seats'/f"{r['electionID']}-{suffix}.html").read_bytes()
        raise ValueError('Unexpected source')
    def test_real_ministerial_tables_reconcile_entire_chambers_and_reuse_bindings(self):
        result=apply_seats(self.elections,self.document,self.fixture)
        for e in result:
            s=e['seats']
            self.assertEqual(sum(g['seats'] for g in s['groups'])+s['unassignedSeats'],s['totalSeats'])
            self.assertEqual(next(g for g in s['groups'] if g['name']=='MOVIMENTO 5 STELLE')['resultID'],'m5s-original')
            self.assertEqual(e['territories'][0]['results'][0]['votes'],123)
            self.assertEqual(s['sourceLabel'],'Eligendo · Archivio')
            self.assertEqual(len(s['sourcePages']),9 if e['id']=='senato-2022' else 3)
        self.assertEqual(next(e['seats'] for e in result if e['id']=='senato-2018')['unassignedSeats'],1)
        camera=next(e['seats'] for e in result if e['id']=='camera-2022')
        self.assertEqual(next(g['seats'] for g in camera['groups'] if g['id']=='seats-centrodestra'),237)
        self.assertEqual(next(g['seats'] for g in camera['groups'] if g['id']=='seats-centrosinistra'),84)
    def test_mixed_components_reconcile_each_coalition_and_single_list(self):
        apply_seats(self.elections,self.document,self.fixture)
        for election in self.elections:
            for group in election['seats']['groups']:
                self.assertEqual(sum(p['seats'] for p in group['components']),group['seats'])
                self.assertTrue(all(p['seats']>0 for p in group['components']))
        current=next(e['seats'] for e in self.elections if e['id']=='camera-2022')
        m5s=next(g for g in current['groups'] if g['id']=='seats-m5s')
        self.assertEqual(m5s['seats'],52)
        self.assertEqual({p['label']:p['seats'] for p in m5s['components']},{'Italia · proporzionale':41,'Italia · uninominale':10,'Estero':1})
        cdx=next(g for g in current['groups'] if g['id']=='seats-centrodestra')
        self.assertEqual(cdx['seats'],237)
        self.assertEqual({p['label']:p['seats'] for p in cdx['components']},{'Italia · proporzionale':114,'Italia · uninominale':121,'Estero':2})

    def test_italia_excludes_valle_daosta_and_estero(self):
        r=self.document['elections'][0];s=r['sources'][0]
        self.assertEqual(sum(b['seats'] for b in parse_page(self.fixture(s['url']),s)),617)
        self.assertNotEqual(617,r['totalSeats'])
    def test_list_metadata_separates_proportional_from_coalition_totals(self):
        for election in self.elections:
            election['territories'][0]['id']='italia'
            election['territories'][0]['results'].append(dict(id='fdi',name="FRATELLI D'ITALIA CON GIORGIA MELONI",votes=12))
        apply_seats(self.elections,self.document,self.fixture)
        current=next(e for e in self.elections if e['id']=='camera-2022')
        fdi=current['territories'][0]['results'][1]
        self.assertEqual(fdi['votes'],12)
        self.assertEqual(fdi['listSeats'],69)
        self.assertEqual(fdi['coalitionID'],'seats-centrodestra')
        self.assertEqual(next(g['seats'] for g in current['seats']['groups'] if g['id']==fdi['coalitionID']),237)
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

    def test_senato_2022_includes_all_six_special_colleges(self):
        result=apply_seats(self.elections,self.document,self.fixture)
        senate=next(e['seats'] for e in result if e['id']=='senato-2022')
        self.assertEqual(senate['totalSeats'],200)
        self.assertEqual(sum(g['seats'] for g in senate['groups']),200)
        self.assertNotIn('314',senate['note'])
        self.assertEqual(next(g['seats'] for g in senate['groups'] if g['id']=='seats-campobase'),1)
        changed=copy.deepcopy(self.document)
        next(r for r in changed['elections'] if r['electionID']=='senato-2022')['sources'].pop()
        with self.assertRaises(ValueError):apply_seats(self.elections,changed,self.fixture)
