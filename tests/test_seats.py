import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from seats import apply_seats

class SeatsTests(unittest.TestCase):
    def setUp(self):
        self.document=json.loads((Path(__file__).resolve().parents[1]/'config/seats.json').read_text())
        self.elections=[dict(id=r['electionID'],chamber=r['seats']['chamber'],territories=[dict(results=[dict(id='m5s-original',name='MOVIMENTO 5 STELLE',votes=123)])]) for r in self.document['elections']]
    def test_reviewed_seats_reconcile_and_reuse_original_result_binding(self):
        result=apply_seats(self.elections,self.document)
        for e in result:
            s=e['seats']
            self.assertEqual(sum(g['seats'] for g in s['groups'])+s['unassignedSeats'],s['totalSeats'])
            m5s=next(g for g in s['groups'] if g['name']=='MOVIMENTO 5 STELLE')
            self.assertEqual(m5s['resultID'],'m5s-original')
            self.assertEqual(e['territories'][0]['results'][0]['votes'],123)
        senato=next(e['seats'] for e in result if e['id']=='senato-2018')
        self.assertEqual(senato['unassignedSeats'],1)
    def test_overallocation_or_duplicate_groups_stop_publication(self):
        for mutation in ['count','duplicate']:
            d=copy.deepcopy(self.document)
            if mutation=='count':d['elections'][0]['seats']['groups'][0]['seats']+=1
            else:d['elections'][0]['seats']['groups'].append(d['elections'][0]['seats']['groups'][0])
            with self.assertRaises(ValueError):apply_seats(self.elections,d)
    def test_wrong_chamber_and_noninstitutional_source_are_rejected(self):
        for field,value in [('chamber','senato'),('sourceURL','https://example.com/seats')]:
            d=copy.deepcopy(self.document);d['elections'][0]['seats'][field]=value
            with self.assertRaises(ValueError):apply_seats(self.elections,d)
    def test_unknown_election_is_not_attached_to_another_year(self):
        self.document['elections'][0]['electionID']='camera-2030'
        with self.assertRaises(ValueError):apply_seats(self.elections,self.document)
