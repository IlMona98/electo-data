import copy
import json
from collections import Counter
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from seat_groups import consolidate_seats
ROOT=Path(__file__).resolve().parents[1]

class SeatGroupingTests(unittest.TestCase):
    def setUp(self):
        self.elections=json.loads((ROOT/'tests/fixtures/seat-groups/original-allocations.json').read_text())
        self.config=json.loads((ROOT/'config/seat-groups.json').read_text())
    def test_every_original_mandate_and_component_is_preserved_once(self):
        originals=copy.deepcopy(self.elections);consolidate_seats(self.elections,self.config)
        for election,old in zip(self.elections,originals):
            s=election['seats'];self.assertEqual(s['originalGroups'],old['seats']['groups'])
            self.assertEqual(sum(g['seats']for g in s['groups'])+s['unassignedSeats'],s['totalSeats'])
            self.assertEqual(len({g['name']for g in s['groups']}),len(s['groups']))
            def components(groups):
                c=Counter()
                for g in groups:
                    for p in g.get('components')or[dict(label=g.get('detail')or'Riparto ministeriale',seats=g['seats'])]:c[p['label']]+=p['seats']
                return c
            self.assertEqual(components(s['groups']),components(s['originalGroups']))
            self.assertEqual(election['territories'],old['territories'])
    def test_old_mixed_ballots_and_foreign_lists_use_one_coalition_row(self):
        consolidate_seats(self.elections,self.config)
        expected={'camera-1994':{'Centrodestra':366,'Progressisti':213,'Patto per l’Italia':46},'camera-1996':{"L’Ulivo":284,'Polo per le Libertà':246},'camera-2001':{'Casa delle Libertà':368},'camera-2008':{'Centrosinistra':246,'Centrodestra':344},'camera-2013':{'Centrosinistra':345,'Centrodestra':125},'senato-2022':{'Centrosinistra':44}}
        for key,groups in expected.items():
            actual={g['name']:g['seats']for g in next(e for e in self.elections if e['id']==key)['seats']['groups']}
            for name,count in groups.items():self.assertEqual(actual.get(name),count,(key,name,actual))
    def test_consolidation_is_idempotent(self):
        consolidate_seats(self.elections,self.config);before=copy.deepcopy(self.elections)
        consolidate_seats(self.elections,self.config);self.assertEqual(self.elections,before)
    def test_ambiguous_memberships_and_missing_originals_fail_atomically(self):
        for mutate in ['missing','duplicate']:
            config=copy.deepcopy(self.config);r=config['elections'][0]
            if mutate=='missing':r['groups'][0]['members'].append('Unknown original group')
            else:r['groups'].append(dict(id='other',name='Other',members=[r['groups'][0]['members'][0]]))
            before=copy.deepcopy(self.elections)
            with self.assertRaises(ValueError):consolidate_seats(self.elections,config)
            self.assertEqual(self.elections,before)
    def test_cyclic_party_coalition_links_are_rejected(self):
        election=dict(id='test',territories=[dict(results=[dict(id='a',coalitionID='b'),dict(id='b',coalitionID='a')])],seats=dict(note='Original',groups=[dict(id='a',name='A',seats=1,resultID='a'),dict(id='b',name='B',seats=1,resultID='b')]))
        with self.assertRaises(ValueError):consolidate_seats([election],dict(schemaVersion=1,elections=[]))
