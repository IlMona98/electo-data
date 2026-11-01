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
        # Display names are owner-editable; identify reviewed allocations by stable ID.
        expected={
            'camera-1994':{'seats-centrodestra':366,'seats-centrosinistra':213,'seats-patto-italia':46},
            'camera-1996':{'seats-centrosinistra':284,'seats-centrodestra':246,'seats-progressisti':35},
            'camera-2001':{'seats-centrodestra':368},
            'camera-2008':{'seats-ab7d0463bb42ee32':246,'seats-d7dd54f7ee52f7c1':344},
            'camera-2013':{'seats-ab7d0463bb42ee32':345,'seats-d7dd54f7ee52f7c1':125},
            'senato-2022':{'seats-centrosinistra':44}}
        for key,groups in expected.items():
            actual={g['id']:g['seats']for g in next(e for e in self.elections if e['id']==key)['seats']['groups']}
            for group_id,count in groups.items():self.assertEqual(actual.get(group_id),count,(key,group_id,actual))
    def test_display_labels_can_change_without_changing_mandates_or_source_names(self):
        baseline=copy.deepcopy(self.elections);consolidate_seats(baseline,self.config)
        config=copy.deepcopy(self.config)
        for election in config['elections']:
            for group in election['groups']:group['name']='Etichetta '+group['id']
        consolidate_seats(self.elections,config)
        for election,old in zip(self.elections,baseline):
            self.assertEqual(election['seats']['originalGroups'],old['seats']['originalGroups'])
            self.assertEqual({g['id']:g['seats']for g in election['seats']['groups']},
                             {g['id']:g['seats']for g in old['seats']['groups']})
            self.assertEqual(election['territories'],old['territories'])
    def test_reviewed_1996_member_keeps_the_original_election_qualifier(self):
        config=copy.deepcopy(self.config)
        record=next(e for e in config['elections']if e['electionID']=='camera-1996')
        group=next(g for g in record['groups']if g['id']=='seats-progressisti')
        self.assertIn('PROGRESSISTI (1996)',group['members'])
        group['members']=['PROGRESSISTI' if n=='PROGRESSISTI (1996)'else n for n in group['members']]
        before=copy.deepcopy(self.elections)
        with self.assertRaisesRegex(ValueError,'PROGRESSISTI'):consolidate_seats(self.elections,config)
        self.assertEqual(self.elections,before)
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
