import copy,gzip,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from vote_pages import build,parse_votes
from seats import apply_seats
ROOT=Path(__file__).resolve().parents[1]
class Votes1948Tests(unittest.TestCase):
    def setUp(self):
        self.configs=[c for c in json.loads((ROOT/'sources.json').read_text())if c['year']==1948]
        self.pages=json.loads(gzip.decompress((ROOT/'tests/fixtures/votes-1948/pages.json.gz').read_bytes()))
    def fetch(self,url):return self.pages[url].encode()
    def test_every_original_territory_reconciles_with_national_turnout_and_votes(self):
        for config in self.configs:
            e=build(config,self.fetch);national=e['territories'][0]
            self.assertEqual(len(e['territories']),32 if e['chamber']=='camera'else 21)
            self.assertEqual(sum(r['votes']for r in national['results']),26264458 if e['chamber']=='camera'else 22657290)
            for field in ['electors','voters']:self.assertEqual(national[field],sum(t[field]for t in e['territories'][1:]))
            for row in national['results']:
                self.assertEqual(row['votes'],sum(r['votes']for t in e['territories'][1:]for r in t['results']if r.get('nationalResultID',r['id'])==row['id']))
            if e['chamber']=='camera':
                self.assertTrue(any(r['name']=='PPST-PPTT'and r.get('nationalResultID')for t in e['territories'][1:]for r in t['results']))
                self.assertTrue(any(r['name']=="MOV.UNITA'D'IT."for t in e['territories'][1:]for r in t['results']))
    def test_full_elective_seats_and_zero_rows_are_read_from_ministerial_tables(self):
        elections=[build(c,self.fetch)for c in self.configs]
        doc=json.loads((ROOT/'config/seats.json').read_text());doc['elections']=[r for r in doc['elections']if r['electionID'].endswith('-1948')]
        apply_seats(elections,doc,self.fetch)
        for e in elections:
            cap=574 if e['chamber']=='camera'else 237
            self.assertEqual(sum(g['seats']for g in e['seats']['groups']),cap)
            self.assertEqual(e['seats']['unassignedSeats'],0)
            dc=next(r for r in e['territories'][0]['results']if r['name']=='DC')
            self.assertEqual(dc['listSeats'],305 if e['chamber']=='camera'else 131)
            self.assertTrue(any(r.get('listSeats')==0 for r in e['territories'][0]['results']))
        bad=copy.deepcopy(doc);bad['elections'][0]['totalSeats']=630
        with self.assertRaises(ValueError):apply_seats(elections,bad,self.fetch)
    def test_block_page_wrong_year_incomplete_territories_and_altered_totals_fail(self):
        config=self.configs[0];url=config['downloadURL'];raw=self.fetch(url)
        for altered in [b'<html>Access denied</html>',raw.replace(b'18/04/1948',b'18/04/1953'),raw.replace(b'26.264.458',b'26.264.459')]:
            with self.assertRaises(ValueError):parse_votes(altered,config,url)
        bad=copy.deepcopy(config);bad['expectedTerritories']-=1
        with self.assertRaises(ValueError):build(bad,self.fetch)
        bad=copy.deepcopy(config);bad.pop('listAliases')
        with self.assertRaises(ValueError):build(bad,self.fetch)
    def test_a_territorial_error_cannot_be_hidden_by_a_correct_national_page(self):
        config=self.configs[0];national=config['downloadURL']
        def corrupt(url):
            data=self.fetch(url)
            return data if url==national else data.replace(b'>DC<',b'>Unreviewed party<',1)
        with self.assertRaises(ValueError):build(config,corrupt)
