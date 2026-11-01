import copy,gzip,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from election_config import read
from vote_pages import build,parse_votes
from seats import apply_seats
ROOT=Path(__file__).resolve().parents[1]
class Votes1953Tests(unittest.TestCase):
    def setUp(self):
        self.ballots=read(ROOT/'config/elections/politiche-19530607.json')['ballots']
        self.pages=json.loads(gzip.decompress((ROOT/'tests/fixtures/votes-1953/pages.json.gz').read_bytes()))
    def fetch(self,url):return self.pages[url].encode()
    def elections(self):
        elections=[build(b['source'],self.fetch)for b in self.ballots]
        apply_seats(elections,dict(schemaVersion=2,elections=[b['seats']for b in self.ballots]),self.fetch)
        return elections
    def test_camera_all_31_constituencies_reconcile_for_every_party_and_turnout(self):
        election=self.elections()[0];national=election['territories'][0]
        self.assertEqual(len(election['territories']),32);self.assertEqual(national['electors'],30272236);self.assertEqual(national['voters'],28406479)
        for key in ['electors','voters']:self.assertEqual(national[key],sum(t[key]for t in election['territories'][1:]))
        for row in national['results']:
            self.assertEqual(row['votes'],sum(r['votes']for t in election['territories'][1:]for r in t['results']if r['id']==row['id']))
        dc=next(r for r in national['results']if r['name']=='DC')
        self.assertEqual((dc['votes'],dc['listSeats']),(10862073,263))
    def test_senate_uses_only_original_national_counts_and_complete_237_elective_seats(self):
        election=self.elections()[1];national=election['territories'][0]
        self.assertEqual(election['territorialCoverage'],'national-only');self.assertEqual(election['sourceUnits'],1)
        self.assertEqual(len(election['territories']),1);self.assertEqual(len(election['sourceDocuments']),1)
        self.assertEqual((national['electors'],national['voters']),(27172871,25483201))
        self.assertEqual(sum(r['votes']for r in national['results']),24296277)
        self.assertEqual(sum(g['seats']for g in election['seats']['groups']),237)
        dc=next(r for r in national['results']if r['name']=='DC');self.assertEqual((dc['votes'],dc['listSeats']),(9660210,112))
        self.assertEqual(next(r for r in national['results']if r['name']=='PRI')['listSeats'],0)
    def test_discordant_regions_are_rejected_instead_of_silently_changing_national_figures(self):
        config=copy.deepcopy(self.ballots[1]['source']);config['nationalOnly']=False;config['expectedTerritories']=19
        config['listAliases']={name:'ALTRI GRUPPI'for name in ['PLI-PRI','DC-PRI','ALTRI','SARDEGNA CON DUE SPIGHE',"PARTITO SARDO D'AZIONE"]}
        with self.assertRaisesRegex(ValueError,'turnout does not reconcile'):build(config,self.fetch)
    def test_national_only_requires_explicit_documented_policy_and_wrong_year_is_rejected(self):
        config=copy.deepcopy(self.ballots[1]['source']);config.pop('nationalOnlyReason')
        with self.assertRaisesRegex(ValueError,'coverage explanation'):build(config,self.fetch)
        config=self.ballots[1]['source'];raw=self.fetch(config['downloadURL']).replace(b'07/06/1953',b'07/06/1958')
        with self.assertRaises(ValueError):parse_votes(raw,config,config['downloadURL'])
    def test_capacities_590_and_237_are_verified_from_actual_seat_rows_not_assumed_by_era(self):
        elections=self.elections();self.assertEqual([e['seats']['totalSeats']for e in elections],[590,237])
        for index,cap in [(0,591),(1,238)]:
            record=copy.deepcopy(self.ballots[index]['seats']);record['totalSeats']=cap
            with self.assertRaisesRegex(ValueError,'chamber incomplete'):
                apply_seats([build(self.ballots[index]['source'],self.fetch)],dict(schemaVersion=2,elections=[record]),self.fetch)
