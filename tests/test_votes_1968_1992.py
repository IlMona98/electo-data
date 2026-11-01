import copy,gzip,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from election_config import read
from vote_pages import build
from seats import apply_seats
ROOT=Path(__file__).resolve().parents[1]
DATES=[(1968,'19680519'),(1972,'19720507'),(1976,'19760620'),(1979,'19790603'),(1983,'19830626'),(1987,'19870614'),(1992,'19920405')]
class Votes1968Through1992Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ballots=[b for _,date in DATES for b in read(ROOT/'config/elections'/f'politiche-{date}.json')['ballots']]
        cls.pages={}
        for year,_ in DATES:cls.pages.update(json.loads(gzip.decompress((ROOT/'tests/fixtures/votes-1968-1992'/f'{year}.json.gz').read_bytes())))
        cls.elections=[build(b['source'],lambda url:cls.pages[url].encode())for b in cls.ballots]
        apply_seats(cls.elections,dict(schemaVersion=2,elections=[b['seats']for b in cls.ballots]),lambda url:cls.pages[url].encode())
    def fetch(self,url):return self.pages[url].encode()
    def test_all_seven_elections_have_both_chambers_and_exact_630_315_seat_allocations(self):
        self.assertEqual(len(self.elections),14)
        for election in self.elections:
            cap=630 if election['chamber']=='camera'else 315
            self.assertEqual(election['seats']['totalSeats'],cap,election['id'])
            self.assertEqual(sum(g['seats']for g in election['seats']['groups']),cap,election['id'])
            self.assertEqual(sum(r['listSeats']for r in election['territories'][0]['results']),cap,election['id'])
            self.assertTrue(any(r['listSeats']==0 for r in election['territories'][0]['results']))
    def test_eleven_full_series_reconcile_each_party_and_original_turnout(self):
        complete=[e for e in self.elections if e.get('territorialCoverage')!='national-only'];self.assertEqual(len(complete),11)
        for election in complete:
            national=election['territories'][0]
            self.assertEqual(len(election['territories']),33 if election['chamber']=='camera'else 21)
            for field in ['electors','voters']:self.assertEqual(national[field],sum(t[field]for t in election['territories'][1:]))
            for row in national['results']:
                self.assertEqual(row['votes'],sum(r['votes']for t in election['territories'][1:]for r in t['results']if r.get('nationalResultID',r['id'])==row['id']),election['id']+': '+row['name'])
    def test_problematic_sources_are_explicitly_national_and_cannot_bypass_full_reconciliation(self):
        national=[e for e in self.elections if e.get('territorialCoverage')=='national-only'];self.assertEqual({e['id']for e in national},{'senato-1987','camera-1992','senato-1992'})
        for election in national:
            self.assertEqual(len(election['territories']),1);self.assertEqual(election['sourceUnits'],1);self.assertEqual(len(election['sourceDocuments']),1)
            source=copy.deepcopy(next(b['source']for b in self.ballots if b['source']['id']==election['id']));source['nationalOnly']=False;source['expectedTerritories']=32 if source['chamber']=='camera'else 20
            with self.assertRaises(ValueError):build(source,self.fetch)
    def test_1979_apostrophe_alias_preserves_original_label_and_requires_explicit_review(self):
        election=next(e for e in self.elections if e['id']=='camera-1979')
        rows=[r for t in election['territories'][1:]for r in t['results']if r['name']=='UNITA DELLA SINISTRA']
        self.assertTrue(rows);self.assertEqual(sum(r['votes']for r in rows),23909)
        self.assertTrue(all(r.get('nationalResultID')for r in rows))
        config=copy.deepcopy(next(b['source']for b in self.ballots if b['source']['id']==election['id']));config.pop('listAliases')
        with self.assertRaisesRegex(ValueError,'Unreviewed territorial voting label'):build(config,self.fetch)
    def test_history_links_stay_in_the_same_chamber_and_follow_the_previous_consultation(self):
        previous=1963
        for year,_ in DATES:
            for ballot in [b for b in self.ballots if b['source']['year']==year]:
                source=ballot['source'];self.assertEqual(source['previousElectionID'],f'{source["chamber"]}-{previous}');self.assertEqual(source['comparisonTerritories'],['national'])
            previous=year
    def test_joint_formations_are_kept_separate_in_the_original_vote_and_seat_rows(self):
        source=next(e for e in self.elections if e['id']=='senato-1968');rows=source['territories'][0]['results']
        self.assertTrue(any(r['name']=='PCI-PSIUP'for r in rows));self.assertFalse(any(r['name']=='PCI'for r in rows))
        self.assertEqual(next(r for r in rows if r['name']=='PCI-PSIUP')['listSeats'],101)
