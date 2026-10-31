import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from publish_identities import publish_registry
from sync import publish

class IdentityPublicationTests(unittest.TestCase):
    def source(self):
        return dict(schemaVersion=1,entities=[
            dict(id='democrazia-cristiana',label='Democrazia Cristiana',shortLabel='DC',kind='party',colorHex='123456',aliases=['DC'],bindings=[],hemicycleOrder=50),
            dict(id='fronte-democratico-popolare',label='Fronte Democratico Popolare',shortLabel='FDP',kind='coalition',colorHex='654321',aliases=['FR.DEMOCR.POPOLARE'],bindings=[])])
    def election(self):
        return dict(id='camera-1948',retrievedAt='2026-10-31T10:00:00Z',checkedAt='2026-10-31T11:00:00Z',
                    territories=[dict(id='italia',electors=1000,voters=900,results=[dict(id='dc',name='DC',votes=500,entityID='outdated'),dict(id='fdp',name='FR.DEMOCR.POPOLARE',votes=300),dict(id='joint',name="UNITA' SOC.-PRI",votes=100)])],
                    seats=dict(totalSeats=574,groups=[dict(id='seats-dc',resultID='dc',name='DC',seats=305)],sourcePages=[dict(url='https://elezionistorico.interno.gov.it/',label='Fonte')]))
    def test_styles_and_embedded_links_update_without_downloading_any_election(self):
        with tempfile.TemporaryDirectory()as folder:
            public=Path(folder);output=public/'v1';old=publish([self.election()],output)
            with patch('urllib.request.urlopen',side_effect=AssertionError('Electoral network must not be used')), patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('Electoral network must not be used')):
                publish_registry(self.source(),public)
            archive=json.loads((output/'archive.json').read_text());rows=archive['elections'][0]['territories'][0]['results']
            self.assertEqual(rows[0]['entityID'],'democrazia-cristiana')
            self.assertEqual(rows[1]['entityID'],'fronte-democratico-popolare')
            self.assertNotIn('entityID',rows[2]) # A joint list is not arbitrarily assigned to one member.
            self.assertEqual(archive['elections'][0]['seats']['groups'][0]['entityID'],'democrazia-cristiana')
            self.assertEqual([r['name']for r in rows],['DC','FR.DEMOCR.POPOLARE',"UNITA' SOC.-PRI"])
            self.assertEqual([r['votes']for r in rows],[500,300,100])
            self.assertEqual(archive['checkedAt'],old['checkedAt'])
            self.assertEqual(archive['retrievedAt'],old['retrievedAt'])
            self.assertEqual(archive['elections'][0]['seats']['totalSeats'],574)
            self.assertEqual(archive['elections'][0]['seats']['sourcePages'],old['elections'][0]['seats']['sourcePages'])
            registry=json.loads((output/'identities.json').read_text())
            self.assertEqual(registry['entities'][0]['colorHex'],'123456')
            self.assertEqual(registry['entities'][0]['hemicycleOrder'],50)
            catalog=json.loads((output/'catalog.json').read_text());entry=catalog['elections'][0]
            payload=(output/entry['path']).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(),entry['sha256'])
            self.assertEqual(json.loads(payload)['elections'][0],archive['elections'][0])
    def test_invalid_identity_keeps_previous_registry_and_verified_results(self):
        with tempfile.TemporaryDirectory()as folder:
            public=Path(folder);output=public/'v1';publish([self.election()],output);publish_registry(self.source(),public)
            before={p.name:p.read_bytes()for p in output.iterdir()}
            invalid=copy.deepcopy(self.source());invalid['entities'][0]['colorHex']='#123456'
            with self.assertRaises(ValueError):publish_registry(invalid,public)
            self.assertEqual({p.name:p.read_bytes()for p in output.iterdir()},before)
    def test_initial_registry_does_not_need_an_electoral_archive(self):
        with tempfile.TemporaryDirectory()as folder:
            publish_registry(self.source(),Path(folder))
            self.assertTrue((Path(folder)/'v1/identities.json').exists())
            self.assertFalse((Path(folder)/'v1/archive.json').exists())
