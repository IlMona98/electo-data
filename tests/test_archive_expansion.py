import copy,json,sys,csv,io
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from aggregate import build
CONFIGS={c['id']:c for c in json.loads((ROOT/'sources.json').read_text())}

class ArchiveExpansionTests(unittest.TestCase):
    def test_catalog_has_every_election_from_1994_in_both_chambers(self):
        years=[1948,1994,1996,2001,2006,2008,2013,2018,2022]
        expected={f'{c}-{y}' for c in ['camera','senato'] for y in years}|{f'europee-{y}' for y in [1994,1999,2004,2009,2014,2019,2024]}
        self.assertEqual(set(CONFIGS),expected)
        for y in years:self.assertEqual(CONFIGS[f'camera-{y}']['eventID'],CONFIGS[f'senato-{y}']['eventID'])
    def test_real_samples_cover_old_headers_units_and_special_vote_types(self):
        for path in sorted((ROOT/'tests/fixtures').glob('*-legacy-sample.csv')):
            with self.subTest(file=path.name):
                key=path.name.replace('-legacy-sample.csv','');config=CONFIGS[key];result=build(path.read_bytes(),config)
                self.assertGreater(len(result['territories']),1)
                self.assertEqual(result['territories'][0]['voters'],sum(t['voters'] for t in result['territories'][1:]))
                self.assertEqual(result['territories'][0]['electors'],sum(t['electors'] for t in result['territories'][1:]))
                self.assertTrue(all(r['votes']>=0 for t in result['territories'] for r in t['results']))
                self.assertNotIn('reviewedVoteExceptions',result)
                if key=='senato-1994':self.assertEqual(result['resultKind'],'groups')
                if key=='camera-1994':self.assertEqual(result['resultKind'],'proportional-lists')
    def test_negative_original_vote_is_exact_reviewed_and_preserved(self):
        raw=(ROOT/'tests/fixtures/camera-1994-legacy-sample.csv').read_bytes();config=copy.deepcopy(CONFIGS['camera-1994'])
        result=build(raw,config);self.assertIn('-7 voti',result['note'])
        party=config['reviewedVoteExceptions'][0]['list']
        expected=sum(int(r['VOTI_LISTA']) for r in csv.DictReader(io.StringIO(raw.decode()),delimiter=';') if r['LISTA'].strip()==party)
        self.assertEqual(next(r['votes'] for r in result['territories'][0]['results'] if r['name']==party),expected)
        config.pop('reviewedVoteExceptions')
        with self.assertRaises(ValueError):build(raw,config)
        changed=raw.replace(b';-7\n',b';-8\n')
        # Match regardless of column ordering in the faithful fixture.
        rows=list(csv.DictReader(io.StringIO(raw.decode()),delimiter=';'))
        for r in rows:
            if r['VOTI_LISTA']=='-7':r['VOTI_LISTA']='-8'
        out=io.StringIO();w=csv.DictWriter(out,fieldnames=list(rows[0]),delimiter=';');w.writeheader();w.writerows(rows)
        with self.assertRaises(ValueError):build(out.getvalue().encode(),CONFIGS['camera-1994'])
    def test_comparison_links_do_not_invent_missing_or_different_chambers(self):
        for source in CONFIGS.values():
            if 'previousElectionID' not in source:continue
            old=CONFIGS[source['previousElectionID']]
            self.assertLess(old['year'],source['year'])
            self.assertEqual(old['category'],source['category'])
            self.assertEqual(old.get('chamber'),source.get('chamber'))
        self.assertNotIn('previousElectionID',CONFIGS['senato-2022'])
        self.assertNotIn('previousElectionID',CONFIGS['senato-2006'])
