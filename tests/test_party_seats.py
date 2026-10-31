import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from party_seats import camera_members, camera_url, official_url, osce_rows, report_counts, apply_party_seats, OSCE

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/party-seats'

class PartySeatsTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'config/party-seats.json').read_text())
        self.camera = copy.deepcopy(next(r for r in self.config['elections'] if r['electionID'] == 'camera-2022'))
        self.camera['expectedMembers'] = 3  # The fixture preserves three original initial mandates and one later replacement.
        self.raw = (FIXTURES / 'camera-sample.json').read_bytes()
        self.text = (FIXTURES / 'osce-2022.txt').read_text()
    def test_real_annex_reconciles_both_chambers_and_separates_foreign_rows(self):
        rows = osce_rows(self.text)
        self.assertEqual(sum(v[0] for area in rows.values() for v in area.values()), 400)
        self.assertEqual(sum(v[1] for area in rows.values() for v in area.values()), 200)
        self.assertEqual(rows['Italia']['Brothers of Italy'], (117, 66))
        self.assertEqual(rows['Estero']['The League-Brothers of Italy- Forza Italia'], (2, 0))
        self.assertEqual(rows['Italia']['Brambilla Michela Vittoria'], (1, 0))
    def test_real_mandates_exclude_later_replacements_and_group_changes(self):
        members = camera_members(self.raw, self.camera)
        self.assertEqual(len(members), 3)
        self.assertEqual(sum(m['name'] == self.camera['jointForeignList'] for m in members), 2)
        mutated = json.loads(self.raw)
        later = next(r for r in mutated['results']['bindings'] if r['start']['value'] > '20221027')
        later['start']['value'] = '20221001'
        with self.assertRaises(ValueError): camera_members(json.dumps(mutated).encode(), self.camera)
    def test_joint_foreign_candidates_are_counted_once_by_initial_affiliation(self):
        members = camera_members(self.raw, self.camera)
        counts, parts = report_counts(osce_rows(self.text), members, self.camera)
        from identities import normalize
        self.assertEqual(counts[normalize("FRATELLI D'ITALIA CON GIORGIA MELONI")], 118)
        self.assertEqual(counts[normalize('LEGA PER SALVINI PREMIER')], 66)
        self.assertEqual(parts[normalize('LEGA PER SALVINI PREMIER')]['Estero · appartenenza iniziale'], 1)
        next(m for m in members if m['name'] == self.camera['jointForeignList'])['groups'] = {'ambiguous', 'other'}
        with self.assertRaises(ValueError): report_counts(osce_rows(self.text), members, self.camera)
    def test_report_corruption_and_unreviewed_names_are_rejected(self):
        for text in [self.text.replace('26.0 117', '26.0 118', 1), self.text.replace('Brambilla Michela Vittoria', 'Removed'), self.text.replace('25 September 2022','25 September 2023')]:
            with self.assertRaises(ValueError): osce_rows(text)
        members = camera_members(self.raw, self.camera)
        with self.assertRaises(ValueError): report_counts(osce_rows(self.text.replace('Brothers of Italy 7,302', 'Unknown party 7,302', 1)), members, self.camera)
    def test_unknown_hosts_and_legislatures_are_rejected(self):
        for url in ['https://evil.example/sparql','https://dati.camera.it@evil.example/sparql','http://dati.camera.it/sparql','https://cdn.osce.org/other.pdf']:
            with self.assertRaises(ValueError): official_url(url)
        with self.assertRaises(ValueError): camera_url(99)
    def test_configuration_contains_dates_aliases_and_no_handwritten_totals(self):
        self.assertEqual(len(self.config['elections']), 7)
        for record in self.config['elections']:
            self.assertNotIn('partyTotals', record)
            self.assertIn('referenceDate', record)
            self.assertTrue(record['note'])
            self.assertTrue('aliases' in record or 'reviewedParties' in record)
    def test_duplicate_parliamentary_rows_do_not_duplicate_mandates(self):
        data = json.loads(self.raw);data['results']['bindings'] *= 2
        self.assertEqual(len(camera_members(json.dumps(data).encode(), self.camera)), 3)
    def test_atomic_enrichment_preserves_votes_and_distinguishes_zero_from_unknown(self):
        from unittest.mock import patch
        from identities import normalize
        record = copy.deepcopy(next(r for r in self.config['elections'] if r['electionID'] == 'senato-2022'))
        names = sorted(set(v for v in record['aliases'].values() if v))
        results = [dict(id=normalize(n),name=n,votes=123,listSeats=0) for n in names]
        results.append(dict(id='unknown',name='Unknown electoral list',votes=12))
        election = dict(id='senato-2022',chamber='senato',year=2022,seats=dict(totalSeats=200),territories=[dict(id='italia',results=results)])
        document = dict(schemaVersion=1,elections=[record])
        with patch('party_seats.pdf_text', return_value=self.text):
            apply_party_seats([election],document,lambda url: b'original-test-document')
        totals = election['seats']['partyTotals']
        self.assertEqual(next(t['seats'] for t in totals if t['name']=='+EUROPA'),0)
        self.assertNotIn('unknown',[t['resultID'] for t in totals])
        self.assertEqual(election['territories'][0]['results'],results)
        before=copy.deepcopy(election)
        bad=copy.deepcopy(record);bad['electionID']='unknown-election'
        with patch('party_seats.pdf_text', return_value=self.text):
            with self.assertRaises(ValueError):apply_party_seats([election],dict(schemaVersion=1,elections=[record,bad]),lambda url:b'original-test-document')
        self.assertEqual(election,before)

    def test_wrong_chamber_is_rejected_before_fetching(self):
        election = dict(id='camera-2022', chamber='senato', seats=dict(totalSeats=400), territories=[])
        doc = dict(schemaVersion=1, elections=[self.camera])
        with self.assertRaises(ValueError): apply_party_seats([election], doc, lambda _: self.fail('Must not fetch an invalid chamber'))

if __name__ == '__main__': unittest.main()
