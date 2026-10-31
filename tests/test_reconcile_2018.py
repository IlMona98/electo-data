import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from party_seats import camera_members
from reconcile_2018 import report_rows,align_rows,vote_rows,senato_members,reconcile
from identities import normalize
ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'tests/fixtures/party-seats'

class Reconciled2018Tests(unittest.TestCase):
    def setUp(self):
        self.records={r['chamber']:r for r in json.loads((ROOT/'config/party-seats.json').read_text())['elections']if r['adapter']=='reconciled-2018'}
        self.elections={e['chamber']:e for e in json.loads((ROOT/'tests/fixtures/seat-groups/original-allocations.json').read_text())if e['id'].endswith('-2018')}
        self.text=(FIX/'osce-2018.txt').read_text()
    def members(self,chamber):
        raw=(FIX/(chamber+'-2018-foreign.json')).read_bytes()
        if chamber=='senato':return senato_members(raw,'20180410',6)
        record=dict(self.records['camera'],expectedMembers=3)
        return camera_members(raw,record)
    def run_reconciliation(self,chamber,election=None,members=None):
        record=self.records[chamber]
        pages=[SimpleNamespace(extract_text=lambda:'6 June 2018')for _ in range(24)]
        pages[22]=SimpleNamespace(extract_text=lambda:self.text,get_contents=lambda:SimpleNamespace(get_data=lambda:b'annex'))
        def fetch(url):
            source=next(s for s in record['ministerialSources']if s['url']==url)
            path=FIX/(chamber+'-2018-votes.html')if source['kind']=='italia'else ROOT/'tests/fixtures/seats'/(chamber+'-2018-'+source['kind']+'.html')
            return path.read_bytes()
        with patch('pypdf.PdfReader',return_value=SimpleNamespace(pages=pages,is_encrypted=False)):
            return reconcile(election or self.elections[chamber],record,b'%PDF-test',members if members is not None else self.members(chamber),fetch)
    def test_four_mislabeled_camera_rows_are_reviewed_against_ministerial_votes(self):
        record=self.records['camera'];source=next(s for s in record['ministerialSources']if s['kind']=='italia')
        aligned,audit=align_rows(report_rows(self.text,'camera'),vote_rows((FIX/'camera-2018-votes.html').read_bytes(),source),record['reviewedReportNames'])
        values={r['name']:r['seats']for r in aligned}
        self.assertEqual(values['FORZA ITALIA'],103)
        self.assertEqual(values['PARTITO DEMOCRATICO'],107)
        self.assertEqual(values['+EUROPA'],2)
        self.assertEqual(values['CIVICA POPOLARE LORENZIN'],2)
        self.assertEqual(next(r['ministerialName']for r in audit if r['reportedName']=='Democratic Party'),'FORZA ITALIA')
    def test_all_party_totals_reconcile_exactly_to_every_coalition_and_full_chamber(self):
        for chamber in ['camera','senato']:
            counts,parts,audit,sources=self.run_reconciliation(chamber)
            allocation=self.elections[chamber]['seats']
            self.assertEqual(sum(counts.values())+sum(r['seats']for r in audit['outsideBallot']),allocation['totalSeats']-allocation['unassignedSeats'])
            self.assertEqual(audit['groupTotals'],{g['id']:g['seats']for g in allocation['groups']})
            self.assertEqual(len(counts),len(self.elections[chamber]['territories'][0]['results']))
            for key,n in counts.items():self.assertEqual(sum(parts[key].values()),n)
            self.assertEqual(len(sources),3)
            self.assertEqual(counts[normalize('FORZA ITALIA')],104 if chamber=='camera'else 57)
            self.assertEqual(counts[normalize('PARTITO DEMOCRATICO')],112 if chamber=='camera'else 53)
            self.assertEqual(counts[normalize('MOVIMENTO 5 STELLE')],227 if chamber=='camera'else 111)
            self.assertEqual(counts[normalize('POTERE AL POPOLO!')],0)
    def test_vacancy_is_not_counted_as_an_occupied_mandate(self):
        rows=report_rows(self.text,'senato')
        self.assertEqual(next(r['seats']for r in rows if r['reportedName']=='Five Star Movement'),112)
        altered=copy.deepcopy(self.elections['senato']);altered['seats']['unassignedSeats']=0
        with self.assertRaises(ValueError):self.run_reconciliation('senato',election=altered)
        with self.assertRaises(ValueError):report_rows(self.text.replace('One seat won by the Five Star Movement in Sicily has remained unassigned','Footnote removed'),'senato')
    def test_unknown_labels_changed_votes_and_inconsistent_coalitions_fail_closed(self):
        record=self.records['camera'];source=next(s for s in record['ministerialSources']if s['kind']=='italia')
        votes=vote_rows((FIX/'camera-2018-votes.html').read_bytes(),source)
        rows=report_rows(self.text,'camera');rows[0]['votes']*=2
        with self.assertRaises(ValueError):align_rows(rows,votes,record['reviewedReportNames'])
        with self.assertRaises(ValueError):align_rows(report_rows(self.text,'camera'),votes,{})
        altered=copy.deepcopy(self.elections['camera']);altered['seats']['groups'][0]['seats']+=1
        with self.assertRaises(ValueError):self.run_reconciliation('camera',election=altered)
    def test_foreign_joint_list_requires_complete_unique_initial_affiliations(self):
        for chamber in ['camera','senato']:
            members=self.members(chamber);self.assertEqual(len(members),3 if chamber=='camera'else 6)
            with self.assertRaises(ValueError):self.run_reconciliation(chamber,members=[])
        with self.assertRaises(ValueError):senato_members((FIX/'senato-2018-foreign.json').read_bytes(),'20180410',314)
