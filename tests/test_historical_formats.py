"""Regression checks against Ministry territorial/national tables (not synthetic totals)."""
import copy
import csv
import io
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from aggregate import build, build_tables, count, decode
ROOT=Path(__file__).resolve().parents[1]
CONFIGS={c['id']:c for c in json.loads((ROOT/'sources.json').read_text())}
FIXTURES=Path(__file__).parent/'fixtures'

def members(config):
    return {config['tables'][k]:(FIXTURES/config['tables'][k]).read_bytes() for k in ['stats','lists','nationalStats','nationalLists']}

def alter(raw, column, value):
    reader=csv.DictReader(io.StringIO(decode(raw)),delimiter=';');rows=list(reader);rows[0][column]=value
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=reader.fieldnames,delimiter=';');writer.writeheader();writer.writerows(rows)
    return output.getvalue().encode()

class HistoricalFormatTests(unittest.TestCase):
    def test_camera_2018_matches_published_national_tables(self):
        config=CONFIGS['camera-2018'];result=build_tables(members(config),config);national=result['territories'][0]
        self.assertEqual(len(result['territories']),28)
        self.assertEqual(national['electors'],46505350)
        self.assertEqual(national['voters'],33923321)
        self.assertEqual(sum(r['votes'] for r in national['results']),32841705)
        self.assertEqual(next(r['votes'] for r in national['results'] if r['name']=='MOVIMENTO 5 STELLE'),10732066)
        self.assertNotIn('tables',result);self.assertNotIn('adapter',result)
    def test_senato_2018_matches_published_national_tables(self):
        config=CONFIGS['senato-2018'];result=build_tables(members(config),config);national=result['territories'][0]
        self.assertEqual(len(result['territories']),20)
        self.assertEqual(national['electors'],42780033)
        self.assertEqual(national['voters'],31231814)
        self.assertEqual(sum(r['votes'] for r in national['results']),30210561)
        self.assertEqual(next(r['votes'] for r in national['results'] if r['name']=='MOVIMENTO 5 STELLE'),9733928)
    def test_wrong_national_vote_cannot_be_published(self):
        config=CONFIGS['camera-2018'];data=members(config);name=config['tables']['nationalLists'];data[name]=alter(data[name],'VOTILISTA','1,00')
        with self.assertRaisesRegex(ValueError,'National and territorial list'):build_tables(data,config)
    def test_wrong_turnout_cannot_be_published(self):
        config=CONFIGS['senato-2018'];data=members(config);name=config['tables']['nationalStats'];data[name]=alter(data[name],'NUMELETTORITOTALI','42780034,00')
        with self.assertRaisesRegex(ValueError,'turnout disagree'):build_tables(data,config)
    def test_missing_territorial_list_is_rejected(self):
        config=CONFIGS['camera-2018'];data=members(config);name=config['tables']['lists'];data[name]=b'\n'.join(data[name].splitlines()[:-1])+b'\n'
        with self.assertRaises(ValueError):build_tables(data,config)
    def test_duplicate_list_is_rejected(self):
        config=CONFIGS['senato-2018'];data=members(config);name=config['tables']['lists'];lines=data[name].splitlines();data[name]=data[name]+lines[1]+b'\n'
        with self.assertRaisesRegex(ValueError,'Duplicate territorial list'):build_tables(data,config)
    def test_decimal_serialization_does_not_round_or_truncate(self):
        self.assertEqual(count('12345,00'),12345)
        self.assertEqual(count('0,00'),0)
        for value in ['12,50','-1','NaN','1.000','1e3']:
            with self.assertRaises(ValueError):count(value)
    def test_reviewed_source_discrepancy_is_preserved_and_disclosed(self):
        config=CONFIGS['europee-2014'];raw=(FIXTURES/'europee-2014-sample.csv').read_bytes();result=build(raw,config)
        self.assertEqual(result['sourceUnits'],2)
        self.assertEqual(result['territories'][0]['electors'],16521+348)
        self.assertEqual(result['territories'][0]['voters'],10022+352)
        self.assertIn('Montescano',result['note'])
        self.assertEqual(len(result['qualityNotes']),1)
        self.assertNotIn('reviewedTurnoutExceptions',result)
        unreviewed=copy.deepcopy(config);unreviewed.pop('reviewedTurnoutExceptions')
        with self.assertRaises(ValueError):build(raw,unreviewed)
    def test_changed_discrepancy_is_not_silently_accepted(self):
        config=copy.deepcopy(CONFIGS['europee-2014']);config['reviewedTurnoutExceptions'][0]['voters']=353
        with self.assertRaises(ValueError):build((FIXTURES/'europee-2014-sample.csv').read_bytes(),config)

if __name__=='__main__':unittest.main()
