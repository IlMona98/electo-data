import json,sys,copy
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from historical_seats import read_table,child_pages,allocation
RECORDS={r['electionID']:r for r in json.loads((ROOT/'config/seats.json').read_text())['elections']}
FIX=ROOT/'tests/fixtures/historical-seats'
class HistoricalSeatTests(unittest.TestCase):
    def test_every_political_record_has_a_complete_seat_source_configuration(self):
        expected={f'{c}-{y}' for c in ['camera','senato'] for y in [1948,1994,1996,2001,2006,2008,2013,2018,2022]}
        self.assertEqual(set(RECORDS),expected)
        for r in RECORDS.values():
            self.assertEqual(r['totalSeats'],(400 if r['chamber']=='camera' else 200) if r['date']=='25/09/2022' else (574 if r['chamber']=='camera' else 237) if r['date']=='18/04/1948' else (630 if r['chamber']=='camera' else 315))
    def test_full_national_flat_table_is_not_proportional_only(self):
        r=RECORDS['senato-2001'];s=r['parts'][0];groups,_=read_table((FIX/'flat-senato-2001.html').read_bytes(),r,s,s['url'])
        self.assertEqual(sum(g['seats'] for g in groups),315)
    def test_separate_2001_camera_components_reconcile_without_double_count(self):
        r=RECORDS['camera-2001']
        def fetch(url):return (FIX/('proportional-camera-2001.html' if url==r['parts'][0]['url'] else 'uninominal-camera-2001.html')).read_bytes()
        value=allocation(r,fetch)
        self.assertEqual(sum(g['seats'] for g in value['groups']),630)
        self.assertEqual({g['detail'] for g in value['groups']},{'Quota proporzionale','Quota uninominale'})
        self.assertEqual(sum(g['seats'] for g in value['groups'] if g['detail']=='Quota proporzionale'),155)
    def test_linked_2013_groups_match_both_coalition_and_chamber_totals(self):
        r=RECORDS['camera-2013'];s=r['parts'][0];raw=(FIX/'linked-camera-2013.html').read_bytes()
        groups,details=read_table(raw,r,s,s['url']);self.assertEqual(sum(g['seats'] for g in groups),617)
        self.assertTrue(any(g['name']=='Centrosinistra' for g in groups))
        self.assertTrue(any('coalitionID' in d for d in details.values()))
        with self.assertRaises(ValueError):read_table(raw.replace(b'>292<',b'>293<',1),r,s,s['url'])
    def test_1994_college_uses_explicit_elected_marker_and_cannot_be_a_municipality(self):
        r=RECORDS['camera-1994'];s=r['parts'][1];raw=(FIX/'college-camera-1994.html').read_bytes()
        # The parser checks the college route and the dated Ministry heading.
        url=s['url'].replace('tpe=A','tpe=L')+'&ne1=1&ne2=110'
        groups,_=read_table(raw,r,s,url);self.assertEqual(sum(g['seats'] for g in groups),1)
        with self.assertRaises(ValueError):read_table(raw.replace(b'Eletto',b''),r,s,url)
        with self.assertRaises(ValueError):read_table(raw,r,s,url.replace('tpe=L','tpe=C'))
    def test_senate_recovery_seat_requires_second_explicit_elected_annotation(self):
        r=RECORDS['senato-2006'];s=r['parts'][2];raw=(FIX/'college-recovery-senato-2006.html').read_bytes()
        url=s['url'].replace('tpe=A','tpe=L')+'&ne1=4&ne2=401'
        groups,_=read_table(raw,r,s,url);self.assertEqual(sum(g['seats'] for g in groups),2)
        self.assertTrue(all('(ELETTO)' not in g['name'] for g in groups))
        with self.assertRaises(ValueError):read_table(raw.replace(b'(ELETTO)',b''),r,s,url)
    def test_college_tree_uses_only_official_selected_election_links(self):
        r=RECORDS['camera-1994'];s=r['parts'][1]
        urls=child_pages((FIX/'college-index-camera-1994.html').read_bytes(),s['url'])
        self.assertEqual(len(urls),27)
        self.assertEqual(len(set(urls)),27)
        self.assertTrue(all('tpel=C' in u and 'dtel=27/03/1994' in u and 'unipro=uni' in u for u in urls))
    def test_coalition_binding_is_shared_by_seat_legend_and_list_stripe(self):
        r=RECORDS['camera-2013'];s=r['parts'][0]
        groups,details=read_table((FIX/'linked-camera-2013.html').read_bytes(),r,s,s['url'])
        from hashlib import sha256
        from identities import normalize,candidate_catalog
        group=next(g for g in groups if g['name']=='Centrosinistra')
        expected='seats-'+sha256((s['id']+':'+normalize(group['name'])).encode()).hexdigest()[:16]
        self.assertTrue(any(d.get('coalitionID')==expected for d in details.values()))
        catalog=candidate_catalog([dict(id='camera-2013',territories=[],seats=dict(groups=[dict(id=expected,name=group['name'])]))])
        self.assertEqual(catalog['candidates'][0]['bindings'],[dict(electionID='camera-2013',resultID=expected)])
