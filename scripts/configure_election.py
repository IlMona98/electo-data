"""Safe incremental onboarding: scaffold -> validate -> isolated preview -> leased apply.
The public snapshot changes only after all selected ballots and territories pass.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import shutil
import zipfile
from aggregate import require
from election_config import (KINDS, encoded, signature, read, load_manifests, load_bundle,
                             compile_manifests, validate_manifest, scaffold, export_legacy, migrate)
from sync import fetch, publish, atomic_write, encode
from identities import compile_registry, apply_identity_links, candidate_catalog
from seats import apply_seats
from party_seats import apply_party_seats
from seat_groups import consolidate_seats
from territory_tree import build_tree
from publish_territories import publish_tree

ROOT=Path(__file__).resolve().parents[1]
STATE='configuration-state.json'

def tree_hash(directory):
    directory=Path(directory); h=sha256()
    for path in sorted(directory.rglob('*')) if directory.exists() else []:
        require(not path.is_symlink(),'Collegamenti simbolici non ammessi nella copia verificata')
        if path.is_file():
            h.update(path.relative_to(directory).as_posix().encode()+b'\0')
            with path.open('rb')as stream:
                while block:=stream.read(1024*1024): h.update(block)
            h.update(b'\0')
    return h.hexdigest()

def engine_hash(root):
    root=Path(root)
    files={p.relative_to(root/'scripts').as_posix():sha256(p.read_bytes()).hexdigest()for p in sorted((root/'scripts').rglob('*.py'))}
    if(root/'requirements.txt').exists():files['requirements.txt']=sha256((root/'requirements.txt').read_bytes()).hexdigest()
    return signature(files)

def inputs_hash(root):
    root=Path(root)
    return signature(dict(config=tree_hash(root/'config'),engine=engine_hash(root),public=tree_hash(root/'public'),requirements=sha256((root/'requirements.txt').read_bytes()).hexdigest() if (root/'requirements.txt').exists()else''))

def validate_snapshot(public):
    public=Path(public); path=public/'v1/archive.json'
    require(path.exists(),'Archivio di partenza assente: serve una copia pubblica verificata, non un archivio vuoto')
    archive=read(path); catalog=read(public/'v1/catalog.json')
    require(archive.get('schemaVersion')==1 and catalog.get('schemaVersion')==1,'Versione archivio non supportata')
    elections=archive['elections']; known={e['id']:e for e in elections}
    require(elections and len(known)==len(elections),'Archivio vuoto o duplicato')
    entries=catalog['elections']
    require(len(entries)==len(known) and {e['id']for e in entries}==set(known),'Catalogo e archivio discordanti')
    for entry in entries:
        require(re.fullmatch(r'[a-z0-9-]+-[a-f0-9]{16}\.json',entry['path']),'Documento catalogo non valido')
        data=(public/'v1'/entry['path']).read_bytes()
        require(sha256(data).hexdigest()==entry['sha256'],'Documento pubblicato corrotto: '+entry['id'])
        require(json.loads(data)['elections']==[known[entry['id']]],'Documento pubblicato diverso dall’archivio: '+entry['id'])
        require(entry['national']==known[entry['id']]['territories'][0],'Riepilogo nazionale discordante')
    return elections

def ballot_digest(ballot):
    return signature(ballot)

def identity_hash(root):
    root=Path(root); path=root/'config/identities.json'; document=read(path); symbols={}
    for entity in document.get('entities',[]):
        name=entity.get('symbolPath')
        if name is None: continue
        require(isinstance(name,str)and re.fullmatch(r'symbols/[a-zA-Z0-9_-]+\.(png|svg)',name),'Percorso simbolo non valido')
        source=root/'public'/name
        symbols[name]=sha256(source.read_bytes()).hexdigest() if source.is_file()else'missing'
    return signature(dict(registry=sha256(path.read_bytes()).hexdigest(),symbols=symbols))

def plan(root):
    root=Path(root); manifests=load_manifests(root); bundle=compile_manifests(manifests)
    baseline=validate_snapshot(root/'public'); published={e['id']:e for e in baseline}
    require(set(published).issubset(s['id']for s in bundle['sources']),'La configurazione rimuoverebbe elezioni pubblicate: rimozione automatica vietata')
    state_path=root/'public/v1'/STATE; state=read(state_path)if state_path.exists()else{}
    receipts=state.get('ballots',{}); engine=engine_hash(root); events=[]
    for manifest in manifests:
        changed=[]
        for ballot in manifest['ballots']:
            key=ballot['source']['id']; receipt=receipts.get(key,{})
            if key not in published or receipt.get('configuration')!=ballot_digest(ballot) or receipt.get('engine')!=engine or receipt.get('sourceSHA256')!=published[key]['sourceSHA256']:
                changed.append(key)
        if changed: events.append(dict(event=manifest['id'],ballots=changed))
    identity=identity_hash(root)
    return dict(events=events,identitiesChanged=state.get('identities')!=identity,engine=engine,
                drafts=[m['id']for m in load_manifests(root,include_drafts=True)if m['status']=='draft'])

def selected_bundle(root, event_ids):
    manifests=load_manifests(root,include_drafts=True)
    require(len(set(event_ids))==len(event_ids)and set(event_ids).issubset(m['id']for m in manifests),'Consultazione sconosciuta o duplicata')
    selected=[m for m in manifests if m['id']in event_ids]
    for m in selected:validate_manifest(m)
    configured=[m for m in manifests if m['status']=='active' or m['id']in event_ids]
    bundle=compile_manifests(configured); ids={b['source']['id']for m in selected for b in m['ballots']}
    subset={'sources':[s for s in bundle['sources']if s['id']in ids]}
    for kind in KINDS:subset[kind]=bundle[kind]|{'elections':[r for r in bundle[kind]['elections']if r['electionID']in ids]}
    return selected,bundle,subset

def report_markdown(report):
    from html import escape
    lines=['# Anteprima delle consultazioni','', '**La preparazione non pubblica dati online.**', '',
           '| Scheda | Voti validi | Votanti | Seggi riportati | Territori dettagliati |',
           '| --- | ---: | ---: | ---: | ---: |']
    for ballot in report['ballots']:
        lines.append('| '+ ' | '.join(str(x) if x is not None else 'Non disponibili' for x in [ballot['id'],ballot['votes'],ballot['voters'],ballot['seats'],ballot['geographicNodes']])+' |')
    lines+=['', 'Schede precedenti preservate: '+str(len(report['preservedBallots']))+'.', '']
    for ballot in report['ballots']:
        lines+=['## '+ballot['id'], '', escape(ballot['dateLabel'])+' · '+escape(ballot['coverage']), '',
                '[Fonte ministeriale](<'+ballot['sourceURL']+'>)', '', 'Impronta della fonte: `'+ballot['sourceSHA256']+'`.', '',
                'Voti nella copia precedente: '+str(ballot['previousVotes'])+'. Voti nella nuova copia: '+str(ballot['votes'])+'.', '',
                'Seggi attesi: '+str(ballot['expectedSeats'])+'. Seggi non riportati: '+str(ballot['unreportedSeats'])+'.', '',
                'Liste prive di identità associata: '+str(len(ballot['unmatchedLists']))+'.']
        if ballot['unmatchedLists']:lines+=['']+['- '+escape(name)for name in ballot['unmatchedLists']]
        lines+=['']
    lines+=report['notes']
    return ('\n'.join(lines)+'\n').encode()

def prepare(root, event_ids, destination, cache=None, fetcher=None):
    root=Path(root); destination=Path(destination); cache=Path(cache or root/'.cache')
    require(not destination.exists(),'La cartella di anteprima esiste già: nessun risultato sovrascritto')
    require(not destination.resolve().is_relative_to((root/'public').resolve()),'L’anteprima deve restare fuori dalla cartella pubblica')
    # Reject configurations and corrupt baselines before making any network requests.
    selected,bundle,subset=selected_bundle(root,event_ids)
    baseline=validate_snapshot(root/'public'); before=inputs_hash(root)
    require({e['id']for e in baseline}.issubset(s['id']for s in bundle['sources']),'Rimozione di elezioni pubblicate non consentita')
    destination.mkdir(parents=True)
    try:
        public=destination/'public'; shutil.copytree(root/'public',public)
        registry=compile_registry(read(root/'config/identities.json'),public)
        results=[]; geography={}
        for source in subset['sources']:
            print('Verifica',source['id'],flush=True)
            election=(fetcher or fetch)(source,cache); results.append(election)
            if not source.get('adapter'):
                key=sha256(source['downloadURL'].encode()).hexdigest(); raw=(cache/(key+'.bin')).read_bytes()
                if source.get('zipMember'):
                    with zipfile.ZipFile(io.BytesIO(raw))as zipped:raw=zipped.read(source['zipMember'])
                # Reuse the bytes already downloaded and verified for votes.
                tree=build_tree(raw,source,election)
                publish_tree(tree,election,public/'v1'); geography[source['id']]=len(tree['nodes'])
            else:
                stale=public/'v1/territories'/source['id']/'index.json'
                if stale.exists():stale.unlink()
                geography[source['id']]=None
        apply_seats(results,subset['seats'])
        apply_party_seats(results,subset['partySeats'])
        consolidate_seats(results,subset['seatGroups'])
        apply_identity_links(results,registry)
        replacements={e['id']:e for e in results}
        merged=[replacements.pop(e['id'],deepcopy(e))for e in baseline]+list(replacements.values())
        # Registry changes apply everywhere, without fetching other electoral sources.
        apply_identity_links(merged,registry)
        registry_changed=identity_hash(root)
        unchanged_ids={e['id']for e in baseline}-set(e['id']for e in results)
        def electoral(value):
            value=deepcopy(value)
            for territory in value['territories']:
                for row in territory['results']:
                    row.pop('entityID',None);row.pop('coalitionEntityID',None)
            for group in value.get('seats',{}).get('groups',[]):group.pop('entityID',None)
            return value
        current={e['id']:e for e in merged}
        require(all(electoral(e)==electoral(current[e['id']])for e in baseline if e['id']in unchanged_ids),'Dati elettorali estranei alla selezione modificati')
        publish(merged,public/'v1')
        atomic_write(public/'v1/identities.json',encode(registry))
        atomic_write(public/'v1/identity-candidates.json',encode(candidate_catalog(merged)))
        state_path=public/'v1'/STATE; state=read(state_path)if state_path.exists()else dict(schemaVersion=1,ballots={})
        state['identities']=registry_changed
        for manifest in selected:
            for ballot in manifest['ballots']:
                key=ballot['source']['id'];state['ballots'][key]=dict(configuration=ballot_digest(ballot),engine=engine_hash(root),sourceSHA256=current[key]['sourceSHA256'])
        atomic_write(state_path,encode(state))
        validate_snapshot(public)
        require(inputs_hash(root)==before,'Configurazione o dati di partenza cambiati durante la preparazione: ripetere il controllo')
        summaries=[]
        for election in results:
            national=election['territories'][0]; old=next((e for e in baseline if e['id']==election['id']),None)
            allocation=election.get('seats',{})
            summaries.append(dict(id=election['id'],year=election['year'],dateLabel=election['dateLabel'],sourceURL=election['sourceURL'],sourceFile=election['sourceFile'],coverage=election['coverage'],previousElectionID=election.get('previousElectionID'),expectedSeats=allocation.get('totalSeats'),unreportedSeats=allocation.get('unreportedSeats'),action='update'if old else'add',sourceSHA256=election['sourceSHA256'],previousVotes=sum(r['votes']for r in old['territories'][0]['results'])if old else None,
                                  votes=sum(r['votes']for r in national['results']),electors=national['electors'],voters=national['voters'],
                                  territories=len(election['territories']),geographicNodes=geography[election['id']],
                                  seats=sum(g['seats']for g in allocation.get('groups',[]))if allocation else None,
                                  previousSourceSHA256=old['sourceSHA256']if old else None,
                                  unmatchedLists=[r['name']for r in national['results']if not r.get('entityID')]))
        report=dict(schemaVersion=1,events=event_ids,inputs=before,output=tree_hash(public),ballots=summaries,
                    preservedBallots=sorted(unchanged_ids),identityLinksUpdated=True,
                    notes=['Liste non associate: simboli e colori restano neutri; nessuna identità assegnata per somiglianza.',
                           'I riepiloghi delle fonti aggregate restano tali: nessun dettaglio comunale inventato.',
                           'Dati preparati, non ancora pubblicati.'])
        markdown=report_markdown(report);atomic_write(destination/'report.md',markdown)
        report['markdownSHA256']=sha256(markdown).hexdigest()
        report['seal']=signature(report)
        atomic_write(destination/'report.json',encoded(report));return report
    except Exception:
        shutil.rmtree(destination);raise

def apply(root, prepared):
    root=Path(root); prepared=Path(prepared);report=read(prepared/'report.json')
    require(report.get('seal')==signature({k:v for k,v in report.items()if k!='seal'}),'Rapporto di anteprima alterato')
    require(report.get('markdownSHA256')==sha256((prepared/'report.md').read_bytes()).hexdigest(),'Riepilogo di anteprima alterato')
    require(report.get('schemaVersion')==1 and report['inputs']==inputs_hash(root),'Anteprima superata: sono cambiati configurazione, codice o dati pubblicati')
    require(report['output']==tree_hash(prepared/'public'),'Anteprima alterata o incompleta')
    validate_snapshot(prepared/'public')
    selected,bundle,_=selected_bundle(root,report['events'])
    # Never remove old immutable documents, symbols or previous elections.
    old={p.relative_to(root/'public')for p in(root/'public').rglob('*')if p.is_file()}
    new={p.relative_to(prepared/'public')for p in(prepared/'public').rglob('*')if p.is_file()}
    allowed_removals={Path('v1/territories')/b['source']['id']/'index.json'for m in selected for b in m['ballots']if b['source'].get('adapter')}
    require(old-new<=allowed_removals,'L’anteprima eliminerebbe documenti precedenti')
    backup=root/'.publication-backup'
    require(not backup.exists(),'Copia di recupero presente: verificare prima di continuare')
    manifest_paths=[root/'config/elections'/f"{m['id']}.json"for m in selected]
    export_paths=[root/'sources.json']+[root/'config'/f'{name}.json'for name in ['seats','party-seats','seat-groups']]
    originals={p:p.read_bytes()if p.exists()else None for p in manifest_paths+export_paths}
    (root/'public').rename(backup)
    try:
        shutil.copytree(prepared/'public',root/'public')
        for manifest,path in zip(selected,manifest_paths):
            manifest['status']='active';atomic_write(path,encoded(manifest))
        export_legacy(root,bundle)
    except BaseException:
        shutil.rmtree(root/'public',ignore_errors=True);backup.rename(root/'public')
        for path,data in originals.items():
            if data is not None:atomic_write(path,data)
            elif path.exists():path.unlink()
        raise
    else:shutil.rmtree(backup)
    return report

def main():
    parser=argparse.ArgumentParser(description='Configura nuove consultazioni senza alterare le altre')
    parser.add_argument('--root',type=Path,default=ROOT)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('migrate');check=sub.add_parser('check');check.add_argument('--event');sub.add_parser('plan')
    new=sub.add_parser('new');new.add_argument('--template',required=True);new.add_argument('--event',required=True);new.add_argument('--year',required=True,type=int);new.add_argument('--date-label',required=True)
    preview=sub.add_parser('prepare');preview.add_argument('--event',action='append',required=True);preview.add_argument('--output',type=Path,required=True)
    install=sub.add_parser('apply');install.add_argument('--prepared',type=Path,required=True)
    run=sub.add_parser('run');run.add_argument('--event',default='');run.add_argument('--mode',choices=['auto','preview','publish','all'],default='auto');run.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=args.root
    if args.command=='migrate':print(migrate(root))
    elif args.command=='new':
        value=scaffold(root,args.template,args.event,args.year,args.date_label)
        path=root/'config/elections'/f'{args.event}.json';atomic_write(path,encoded(value));print('Bozza creata:',path)
    elif args.command=='check':
        bundle=selected_bundle(root,[args.event])[1] if args.event else load_bundle(root);print('Configurazione verificata:',len(bundle['sources']),'schede. Bozze escluse dalla pubblicazione automatica.')
    elif args.command=='plan':print(json.dumps(plan(root),ensure_ascii=False,indent=2))
    elif args.command=='prepare':print(json.dumps(prepare(root,args.event,args.output),ensure_ascii=False,indent=2))
    elif args.command=='apply':print(json.dumps(apply(root,args.prepared),ensure_ascii=False,indent=2))
    else:
        selected_plan=plan(root)
        if args.event:events=[args.event]
        elif args.mode=='all':events=[m['id']for m in load_manifests(root)]
        else:events=[r['event']for r in selected_plan['events']]
        require(args.mode not in ('preview','publish')or bool(args.event),'Selezionare la consultazione da preparare o pubblicare')
        if not events and not selected_plan['identitiesChanged']:
            print('Nessuna fonte da rielaborare. Bozze:',', '.join(selected_plan['drafts'])or'nessuna');return
        report=prepare(root,events,args.output)
        if args.mode!='preview':apply(root,args.output)
        print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
