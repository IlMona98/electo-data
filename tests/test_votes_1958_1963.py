import copy,gzip,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from election_config import read
from vote_pages import build,parse_votes
from historical_seats import child_pages
from seats import apply_seats
ROOT=Path(__file__).resolve().parents[1]
class Votes1958And1963Tests(unittest.TestCase):
    def setUp(self):
        self.ballots=[b for event in ['politiche-19580525','politiche-19630428']for b in read(ROOT/'config/elections'/f'{event}.json')['ballots']]
        self.pages=json.loads(gzip.decompress((ROOT/'tests/fixtures/votes-1958-1963/pages.json.gz').read_bytes()))
    def fetch(self,url):return self.pages[url].encode()
    def elections(self):
        elections=[build(b['source'],self.fetch)for b in self.ballots]
        apply_seats(elections,dict(schemaVersion=2,elections=[b['seats']for b in self.ballots]),self.fetch)
        return elections
    def test_three_complete_territorial_series_reconcile_every_vote_and_turnout(self):
        for election in self.elections():
            if election['id']=='senato-1958':continue
            expected=20 if election['id']=='senato-1963'else 33
            self.assertEqual(len(election['territories']),expected)
            national=election['territories'][0]
            for field in ['electors','voters']:self.assertEqual(national[field],sum(t[field]for t in election['territories'][1:]))
            for row in national['results']:
                self.assertEqual(row['votes'],sum(r['votes']for t in election['territories'][1:]for r in t['results']if r.get('nationalResultID',r['id'])==row['id']))
    def test_all_four_complete_seat_allocations_include_explicit_zeros(self):
        expected={'camera-1958':596,'senato-1958':246,'camera-1963':630,'senato-1963':315}
        for election in self.elections():
            cap=expected[election['id']]
            self.assertEqual(election['seats']['totalSeats'],cap)
            self.assertEqual(sum(g['seats']for g in election['seats']['groups']),cap)
            self.assertTrue(any(r['listSeats']==0 for r in election['territories'][0]['results']))
            self.assertEqual(sum(r['listSeats']for r in election['territories'][0]['results']),cap)
    def test_1958_senate_keeps_original_national_psi_and_rejects_the_100_vote_discrepancy(self):
        source=next(b['source']for b in self.ballots if b['source']['id']=='senato-1958')
        election=build(source,self.fetch);national=election['territories'][0]
        self.assertEqual(election['territorialCoverage'],'national-only');self.assertEqual(len(election['territories']),1)
        psi=next(r for r in national['results']if r['name']=='PSI');self.assertEqual(psi['votes'],3682945)
        regions=[parse_votes(self.fetch(u),source,u)for u in child_pages(self.fetch(source['downloadURL']),source['downloadURL'])]
        self.assertEqual(sum(r['votes']for t in regions for r in t['results']if r['name']=='PSI'),psi['votes']+100)
        config=copy.deepcopy(source);config['nationalOnly']=False;config['expectedTerritories']=19
        with self.assertRaisesRegex(ValueError,'territorial votes do not reconcile'):build(config,self.fetch)
    def test_previous_elections_are_same_branch_and_immediately_preceding_configured_year(self):
        for ballot in self.ballots:
            source=ballot['source'];previous=1953 if source['year']==1958 else 1958
            self.assertEqual(source['previousElectionID'],source['chamber']+'-'+str(previous))
            self.assertEqual(source['comparisonTerritories'],['national'])
