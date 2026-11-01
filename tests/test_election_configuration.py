from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from election_config import (migrate, legacy_bundle, load_bundle, load_manifests, compile_manifests,
                             encoded, scaffold, validate_manifest, export_legacy)
from configure_election import prepare, apply, plan, tree_hash, engine_hash, ballot_digest, identity_hash, STATE
from sync import publish
from aggregate import build
from test_pipeline import CONFIG,ROWS,data

ROOT=Path(__file__).resolve().parents[1]
STAMP=dict(retrievedAt='2026-10-28T10:00:00Z',checkedAt='2026-10-28T11:00:00Z')

class ElectionConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'repository';self.root.mkdir()
        (self.root/'config/elections').mkdir(parents=True);(self.root/'scripts').mkdir()
        (self.root/'public/v1').mkdir(parents=True)
        (self.root/'config/identities.json').write_bytes(encoded(dict(schemaVersion=1,entities=[])))
        elections=[]
        for order,year in enumerate([2019,2024]):
            source=deepcopy(CONFIG)|dict(id=f'europee-{year}',year=year,dateLabel=str(year),downloadURL=f'https://elezionistorico.interno.gov.it/daithome/documenti/opendata/{year}.csv')
            manifest=dict(schemaVersion=1,id=source['id'],status='active',ballots=[dict(order=order,source=source,seatsPolicy='not-applicable')])
            (self.root/'config/elections'/f"{source['id']}.json").write_bytes(encoded(manifest))
            elections.append(build(data(ROWS),source)|STAMP)
        publish(elections,self.root/'public/v1')
        export_legacy(self.root,load_bundle(self.root))
        state=dict(schemaVersion=1,identities=identity_hash(self.root),ballots={})
        for m in load_manifests(self.root):
            b=m['ballots'][0];e=next(e for e in elections if e['id']==b['source']['id'])
            state['ballots'][e['id']]=dict(configuration=ballot_digest(b),engine=engine_hash(self.root),sourceSHA256=e['sourceSHA256'])
        (self.root/'public/v1'/STATE).write_bytes(encoded(state))
        self.output=Path(self.temp.name)/'preview';self.cache=self.root/'.cache'
    def change(self,identity='europee-2024'):
        path=self.root/'config/elections'/f'{identity}.json';m=json.loads(path.read_text())
        m['ballots'][0]['source']['note']+=' verified revision';path.write_bytes(encoded(m))
    def fetcher(self,source,cache):
        rows=deepcopy(ROWS);rows[0][3]='31';payload=data(rows)
        cache.mkdir(exist_ok=True);(cache/(sha256(source['downloadURL'].encode()).hexdigest()+'.bin')).write_bytes(payload)
        return build(payload,source)|STAMP
    def preview(self,events=None):
        return prepare(self.root,events or ['europee-2024'],self.output,self.cache,self.fetcher)
    def test_existing_configuration_migrates_without_changing_a_single_field_or_array_order(self):
        root=Path(self.temp.name)/'legacy';(root/'config').mkdir(parents=True)
        shutil.copy2(ROOT/'sources.json',root/'sources.json')
        for name in ['seats','party-seats','seat-groups']:shutil.copy2(ROOT/'config'/f'{name}.json',root/'config'/f'{name}.json')
        original=legacy_bundle(root);expected=(len({s.get('eventID',s['id'])for s in original['sources']}),len(original['sources']))
        self.assertEqual(migrate(root),expected);self.assertEqual(load_bundle(root),original)
        with self.assertRaises(ValueError):migrate(root)
    def test_plan_only_selects_changed_event_and_keeps_camera_and_senate_together(self):
        self.assertEqual(plan(self.root)['events'],[]);self.change()
        self.assertEqual(plan(self.root)['events'],[dict(event='europee-2024',ballots=['europee-2024'])])
        politics=next(m for m in load_manifests(ROOT)if m['id']=='politiche-20220925')
        self.assertEqual({b['source']['chamber']for b in politics['ballots']},{'camera','senato'})
        politics['ballots'].pop()
        with self.assertRaisesRegex(ValueError,'insieme'):validate_manifest(politics)
    def test_draft_never_enters_automatic_refresh_and_inherits_no_old_exceptions(self):
        draft=scaffold(self.root,'europee-2024','europee-2029',2029,'10 giugno 2029')
        (self.root/'config/elections/europee-2029.json').write_bytes(encoded(draft))
        self.assertEqual(len(load_bundle(self.root)['sources']),2)
        self.assertEqual(plan(self.root)['events'],[]);self.assertEqual(plan(self.root)['drafts'],['europee-2029'])
        source=draft['ballots'][0]['source']
        self.assertEqual(source['downloadURL'],'')
        for key in ['previousElectionID','comparisonAliases','reviewedVoteExceptions','reviewedTurnoutExceptions','zipMember']:
            self.assertNotIn(key,source)
        with self.assertRaises(ValueError):validate_manifest(draft)
    def test_preview_downloads_only_selected_ballot_and_never_changes_public_files(self):
        before=tree_hash(self.root/'public'); spy=Mock(side_effect=self.fetcher)
        report=prepare(self.root,['europee-2024'],self.output,self.cache,spy)
        self.assertEqual(spy.call_count,1);self.assertEqual(tree_hash(self.root/'public'),before)
        self.assertEqual(report['preservedBallots'],['europee-2019'])
        self.assertEqual(report['ballots'][0]['votes'],76)
        self.assertGreater(report['ballots'][0]['geographicNodes'],0)
    def test_apply_preserves_old_ballot_and_every_immutable_document_then_plan_is_empty(self):
        old=json.loads((self.root/'public/v1/archive.json').read_text())['elections'][0]
        paths={p.relative_to(self.root/'public')for p in(self.root/'public').rglob('*.json')}
        self.change();self.preview();apply(self.root,self.output)
        current=json.loads((self.root/'public/v1/archive.json').read_text())['elections']
        self.assertEqual(current[0],old);self.assertEqual(len(current),2)
        self.assertTrue(all((self.root/'public'/p).exists()for p in paths))
        self.assertEqual(plan(self.root)['events'],[])
    def test_changed_inputs_reject_an_old_preview(self):
        self.preview();self.change();before=tree_hash(self.root/'public')
        with self.assertRaisesRegex(ValueError,'Anteprima superata'):apply(self.root,self.output)
        self.assertEqual(tree_hash(self.root/'public'),before)
    def test_modified_output_or_report_cannot_publish(self):
        self.preview();path=self.output/'public/v1/archive.json';path.write_bytes(path.read_bytes()+b' ')
        before=tree_hash(self.root/'public')
        with self.assertRaisesRegex(ValueError,'alterata'):apply(self.root,self.output)
        self.assertEqual(tree_hash(self.root/'public'),before)
        report=json.loads((self.output/'report.json').read_text());report['events']=[]
        (self.output/'report.json').write_bytes(encoded(report))
        with self.assertRaisesRegex(ValueError,'Rapporto'):apply(self.root,self.output)
    def test_any_failed_ballot_preserves_everything_and_removes_partial_preview(self):
        before=tree_hash(self.root/'public');spy=Mock(side_effect=[self.fetcher(load_bundle(self.root)['sources'][0],self.cache),ValueError('Source failed')])
        with self.assertRaisesRegex(ValueError,'Source failed'):prepare(self.root,['europee-2019','europee-2024'],self.output,self.cache,spy)
        self.assertEqual(tree_hash(self.root/'public'),before);self.assertFalse(self.output.exists())
    def test_invalid_source_and_corrupt_baseline_fail_before_any_download(self):
        path=self.root/'config/elections/europee-2024.json';m=json.loads(path.read_text());m['ballots'][0]['source']['downloadURL']='https://example.com/x';path.write_bytes(encoded(m))
        spy=Mock()
        with self.assertRaises(ValueError):prepare(self.root,['europee-2024'],self.output,self.cache,spy)
        spy.assert_not_called()
        m['ballots'][0]['source']['downloadURL']=CONFIG['sourceURL'];path.write_bytes(encoded(m))
        catalog=json.loads((self.root/'public/v1/catalog.json').read_text());catalog['elections'][0]['sha256']='0'*64
        (self.root/'public/v1/catalog.json').write_bytes(encoded(catalog))
        with self.assertRaisesRegex(ValueError,'corrotto'):prepare(self.root,['europee-2024'],self.output,self.cache,spy)
        spy.assert_not_called()
    def test_engine_change_invalidates_receipts_but_not_formatting_of_cache_files(self):
        (self.root/'scripts/parser.py').write_text('version = 2\n')
        self.assertEqual(len(plan(self.root)['events']),2)
    def test_published_election_cannot_disappear_from_configuration(self):
        (self.root/'config/elections/europee-2019.json').unlink()
        with self.assertRaisesRegex(ValueError,'rimuoverebbe'):plan(self.root)
    def test_unreviewed_previous_consultation_and_duplicate_order_are_rejected(self):
        path=self.root/'config/elections/europee-2024.json';m=json.loads(path.read_text());m['ballots'][0]['source']['previousElectionID']='unknown';path.write_bytes(encoded(m))
        with self.assertRaisesRegex(ValueError,'precedente sconosciuta'):load_bundle(self.root)
        m['ballots'][0]['source'].pop('previousElectionID');m['ballots'][0]['order']=0;path.write_bytes(encoded(m))
        with self.assertRaisesRegex(ValueError,'Ordine'):load_bundle(self.root)
    def test_installation_failure_rolls_back_public_snapshot_and_configuration(self):
        self.preview();before=tree_hash(self.root/'public');config=tree_hash(self.root/'config')
        with patch('configure_election.export_legacy',side_effect=OSError('disk error')):
            with self.assertRaises(OSError):apply(self.root,self.output)
        self.assertEqual(tree_hash(self.root/'public'),before);self.assertEqual(tree_hash(self.root/'config'),config)
        self.assertFalse((self.root/'.publication-backup').exists())
    def test_preview_inside_public_tree_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'fuori'):prepare(self.root,['europee-2024'],self.root/'public/preview',self.cache,self.fetcher)
    def test_identity_only_update_does_not_download_votes(self):
        path=self.root/'config/identities.json';path.write_bytes(encoded(dict(schemaVersion=1,entities=[]))+b' ')
        self.assertTrue(plan(self.root)['identitiesChanged']);self.assertEqual(plan(self.root)['events'],[])
        spy=Mock();prepare(self.root,[],self.output,self.cache,spy);spy.assert_not_called()
        apply(self.root,self.output);self.assertFalse(plan(self.root)['identitiesChanged'])

    def test_completed_draft_is_activated_only_after_a_verified_installation(self):
        draft=scaffold(self.root,'europee-2024','europee-2029',2029,'10 giugno 2029')
        source=draft['ballots'][0]['source'];source.update(coverage='Italia',note='Perimetro verificato',sourceURL=CONFIG['sourceURL'],sourceFile='test.csv',downloadURL=CONFIG['sourceURL'])
        path=self.root/'config/elections/europee-2029.json';path.write_bytes(encoded(draft))
        self.preview(['europee-2029']);self.assertEqual(json.loads(path.read_text())['status'],'draft')
        apply(self.root,self.output);self.assertEqual(json.loads(path.read_text())['status'],'active')
        self.assertEqual(len(json.loads((self.root/'public/v1/archive.json').read_text())['elections']),3)
        self.assertEqual(plan(self.root)['events'],[])
    def test_selecting_one_political_event_checks_both_chambers(self):
        event='politiche-2022';manifest=dict(schemaVersion=1,id=event,status='active',ballots=[])
        for order,chamber in enumerate(['camera','senato'],start=2):
            source=deepcopy(CONFIG)|dict(id=chamber+'-2022',year=2022,category='politiche',dateLabel='25 settembre 2022',eventID=event,chamber=chamber,downloadURL=CONFIG['sourceURL'])
            manifest['ballots'].append(dict(order=order,source=source,seatsPolicy='unavailable',seatsUnavailableReason='Riparti non disponibili nella fonte di test'))
        (self.root/'config/elections'/f'{event}.json').write_bytes(encoded(manifest))
        spy=Mock(side_effect=self.fetcher)
        report=prepare(self.root,[event],self.output,self.cache,spy)
        self.assertEqual(spy.call_count,2);self.assertEqual({r['id']for r in report['ballots']},{'camera-2022','senato-2022'})
        self.assertEqual(report['preservedBallots'],['europee-2019','europee-2024'])
    def test_owner_symbol_change_schedules_identity_update_without_electoral_downloads(self):
        path=self.root/'config/identities.json';symbols=self.root/'public/symbols';symbols.mkdir()
        symbol=symbols/'party.svg';symbol.write_text('<svg/>')
        path.write_bytes(encoded(dict(schemaVersion=1,entities=[dict(id='party',label='Partito',shortLabel='P',kind='party',colorHex='123456',aliases=[],bindings=[],symbolPath='symbols/party.svg')])))
        state_path=self.root/'public/v1'/STATE;state=json.loads(state_path.read_text());state['identities']=identity_hash(self.root);state_path.write_bytes(encoded(state))
        self.assertFalse(plan(self.root)['identitiesChanged'])
        symbol.write_text('<svg width="512"/>')
        self.assertTrue(plan(self.root)['identitiesChanged']);self.assertEqual(plan(self.root)['events'],[])
    def test_new_public_documents_after_preview_cannot_be_lost_by_installation(self):
        self.preview();path=self.root/'public/v1/older-document.json';path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'Anteprima superata'):apply(self.root,self.output)
        self.assertTrue(path.exists())
