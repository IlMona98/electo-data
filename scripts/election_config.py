"""One manifest per electoral event; lossless compatibility with existing adapters."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
from aggregate import require

KINDS = {'seats': 2, 'partySeats': 1, 'seatGroups': 1}
LEGACY = {'seats': 'seats', 'partySeats': 'party-seats', 'seatGroups': 'seat-groups'}
SOURCE_KEYS = set('adapter category chamber columns comparisonAliases comparisonTerritories coverage date dateLabel downloadURL eventID expectedTerritories headingPrefix id level listAliases note nationalOnly nationalOnlyReason previousElectionID resultKind reviewedTurnoutExceptions reviewedVoteExceptions sourceFile sourceURL tables title type unit year zipMember'.split())

def read(path):
    return json.loads(Path(path).read_text())

def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()

def signature(value):
    return sha256(encoded(value)).hexdigest()

def legacy_bundle(root):
    root = Path(root)
    return {'sources': read(root/'sources.json')} | {k: read(root/'config'/f'{v}.json') for k,v in LEGACY.items()}

def migrate(root, destination=None):
    """No adapter field, ordering, reviewed exception or identity binding is rewritten."""
    root = Path(root); destination = Path(destination or root/'config/elections')
    require(not destination.exists(), 'La destinazione esiste già: nessun file sovrascritto')
    bundle = legacy_bundle(root); events = {}; ballots = {}
    for order, source in enumerate(bundle['sources']):
        event = source.get('eventID', source['id'])
        manifest = events.setdefault(event, dict(schemaVersion=1, id=event, status='active', ballots=[]))
        ballot = dict(order=order, source=deepcopy(source), seatsPolicy='configured' if source['category']=='politiche' else 'not-applicable')
        require(source['id'] not in ballots, 'Scheda duplicata nella configurazione originale')
        ballots[source['id']] = ballot; manifest['ballots'].append(ballot)
    for kind in KINDS:
        for order, record in enumerate(bundle[kind]['elections']):
            require(record['electionID'] in ballots and kind not in ballots[record['electionID']], 'Riparto originale sconosciuto o duplicato')
            ballots[record['electionID']][kind] = deepcopy(record)
            ballots[record['electionID']][kind+'Order'] = order
    destination.mkdir(parents=True)
    try:
        for event, value in events.items():
            require(re.fullmatch('[a-z0-9-]+', event), 'ID consultazione non valido')
            (destination/(event+'.json')).write_bytes(encoded(value))
        compiled = compile_manifests(load_manifests(root, directory=destination))
        require(compiled == bundle, 'La migrazione altererebbe la configurazione originale')
    except Exception:
        import shutil
        shutil.rmtree(destination)
        raise
    return len(events), len(ballots)

def validate_source(source):
    from sync import official_url
    require(isinstance(source, dict) and not set(source)-SOURCE_KEYS, 'Campo fonte sconosciuto: '+str(set(source)-SOURCE_KEYS))
    for key in ['id','title','dateLabel','coverage','note','sourceURL','sourceFile']:
        require(isinstance(source.get(key),str) and source[key].strip(), 'Campo fonte mancante: '+key)
    require(re.fullmatch('[a-z0-9-]+', source['id']), 'ID scheda non valido')
    require(type(source.get('year')) is int and 1861<=source['year']<=2100, 'Anno non valido')
    require(source.get('category') in ('politiche','europee'), 'Tipo di elezione non supportato')
    adapter = source.get('adapter', 'csv')
    require(adapter in ('csv','aggregate-tables','historical-vote-pages'), 'Formato non supportato: serve un adattatore verificato')
    if source.get('nationalOnly') is not None:
        require(adapter=='historical-vote-pages'and type(source['nationalOnly'])is bool,'Copertura solo nazionale non supportata per questo adattatore')
        if source['nationalOnly']:require(bool(source.get('nationalOnlyReason'))and source['nationalOnlyReason']in source['note'],'Motivare la copertura solo nazionale')
    if adapter == 'historical-vote-pages':
        from seats import official_page
        q = official_page(source['sourceURL'])
        require(q['dtel'][0] == source.get('date') and int(q['dtel'][0][-4:])==source['year'], 'Data fonte non coerente')
    else:
        official_url(source.get('downloadURL','')); official_url(source['sourceURL'])
        if adapter == 'csv':
            columns=source.get('columns',[]); units=source.get('unit',[])
            require(isinstance(columns,list) and len(columns)==6 and all(isinstance(x,str) and x for x in columns) and len(set(columns))==6, 'Servono sei colonne distinte per regione, comune, lista, voti, elettori e votanti')
            require(isinstance(units,list) and units and all(isinstance(x,str) and x for x in units) and len(set(units))==len(units), 'Unità territoriali mancanti o duplicate')
            require(bool(source.get('level')), 'Livello territoriale mancante')
        else:
            require(set(source.get('tables',{})) == {'stats','lists','nationalStats','nationalLists','statsKey','listsKey'} and len({source['tables'][k] for k in ['stats','lists','nationalStats','nationalLists']})==4, 'Tabelle aggregate incomplete o duplicate')

def validate_manifest(manifest):
    require(manifest.get('schemaVersion')==1 and re.fullmatch('[a-z0-9-]+',manifest.get('id','')), 'Manifest non valido')
    require(not set(manifest)-{'schemaVersion','id','status','ballots'}, 'Campo manifest sconosciuto')
    require(manifest.get('status') in ('draft','active') and isinstance(manifest.get('ballots'),list) and manifest['ballots'], 'Stato o schede mancanti')
    sources=[]
    for ballot in manifest['ballots']:
        require(not set(ballot)-({'source','order','seatsPolicy','seatsUnavailableReason'}|set(KINDS)|{k+'Order' for k in KINDS}), 'Campo scheda sconosciuto')
        require(type(ballot.get('order')) is int and ballot['order']>=0, 'Ordinamento scheda non valido')
        source=ballot['source']; validate_source(source); sources.append(source)
        if source['category']=='politiche':
            require(source.get('chamber') in ('camera','senato') and source.get('eventID')==manifest['id'], 'Ramo o consultazione politica non coerente')
            require(ballot.get('seatsPolicy') in ('configured','unavailable'), 'Specificare i seggi oppure dichiararli non disponibili')
            if ballot['seatsPolicy']=='unavailable':
                require(bool(ballot.get('seatsUnavailableReason')) and 'seats' not in ballot and 'partySeats' not in ballot and 'seatGroups' not in ballot, 'Motivare i seggi non disponibili senza aggiungere riparti')
            else: require('seats' in ballot, 'Configurazione dei seggi mancante')
        else: require(ballot.get('seatsPolicy')=='not-applicable' and not any(k in ballot for k in KINDS), 'Riparti politici applicati alle Europee')
        for kind in KINDS:
            if kind not in ballot: continue
            record=ballot[kind]
            require(record.get('electionID')==source['id'], 'Riparto associato alla scheda sbagliata')
            if kind!='seatGroups': require(record.get('chamber')==source.get('chamber'), 'Riparto associato al ramo sbagliato')
            if kind=='seats':
                require(type(record.get('totalSeats')) is int and 1<=record['totalSeats']<=1000, 'Capienza non valida')
                require(record.get('type')=={'camera':'C','senato':'S'}[source['chamber']], 'Tipo di ramo errato nei seggi')
                require(str(source['year']) in record.get('date',''), 'Anno dei seggi diverso dai voti')
            require(type(ballot.get(kind+'Order',ballot['order'])) is int, 'Ordine riparto non valido')
    require(len({s['id']for s in sources})==len(sources), 'Scheda duplicata nella consultazione')
    require(len({(s['year'],s['category'],s['dateLabel'])for s in sources})==1, 'Schede di consultazioni diverse nello stesso file')
    if sources[0]['category']=='politiche': require({s['chamber']for s in sources}=={'camera','senato'} and len(sources)==2, 'Le politiche devono configurare Camera e Senato insieme')
    else: require(len(sources)==1 and manifest['id']==sources[0]['id'], 'Europee: una sola scheda per consultazione')

def load_manifests(root, include_drafts=False, directory=None):
    directory=Path(directory or Path(root)/'config/elections'); manifests=[]
    for path in sorted(directory.glob('*.json')):
        value=read(path)
        require(path.stem==value.get('id') and value.get('schemaVersion')==1 and value.get('status')in('draft','active'), 'Nome, versione o stato del manifest non validi: '+path.name)
        if value['status']=='draft' and not include_drafts: continue
        if value['status']=='active': validate_manifest(value)
        manifests.append(value)
    require(len({m['id']for m in manifests})==len(manifests),'Consultazione duplicata')
    return manifests

def compile_manifests(manifests):
    ballots=[b for m in manifests for b in m['ballots']]
    require(len({b['source']['id']for b in ballots})==len(ballots),'ID scheda duplicato tra consultazioni')
    require(len({b['order']for b in ballots})==len(ballots),'Ordine scheda duplicato')
    sources=[b['source']for b in sorted(ballots,key=lambda b:b['order'])]
    known={s['id']:s for s in sources}
    for source in sources:
        previous=source.get('previousElectionID')
        if not previous: continue
        require(previous in known,'Consultazione precedente sconosciuta: '+previous)
        before=known[previous]
        require(before['year']<source['year'] and before['category']==source['category'] and before.get('chamber')==source.get('chamber') and before.get('resultKind','lists')==source.get('resultKind','lists'), 'Confronto tra anni, rami o tipi di voto incompatibili')
    bundle={'sources':sources}
    for kind,version in KINDS.items():
        subset=[b for b in ballots if kind in b]
        orders=[b.get(kind+'Order',b['order'])for b in subset]
        require(len(set(orders))==len(orders),'Ordine duplicato: '+kind)
        bundle[kind]=dict(schemaVersion=version,elections=[b[kind]for b in sorted(subset,key=lambda b:b.get(kind+'Order',b['order']))])
    return bundle

def load_bundle(root):
    directory=Path(root)/'config/elections'
    return compile_manifests(load_manifests(root)) if directory.exists() else legacy_bundle(root)

def export_legacy(root, bundle):
    from sync import atomic_write
    root=Path(root); atomic_write(root/'sources.json',encoded(bundle['sources']))
    for kind,name in LEGACY.items(): atomic_write(root/'config'/f'{name}.json',encoded(bundle[kind]))

def scaffold(root, template_id, event_id, year, date_label):
    require(re.fullmatch('[a-z0-9-]+',event_id) and type(year)is int and 1861<=year<=2100 and date_label.strip(), 'ID, anno o data non validi')
    manifests=load_manifests(root,include_drafts=True)
    template=next((m for m in manifests if m['id']==template_id),None)
    require(template is not None and template['status']=='active','Modello verificato non trovato')
    require(not any(m['id']==event_id for m in manifests),'Consultazione già esistente')
    require(all(not b['source'].get('adapter') for b in template['ballots']),'Questo formato speciale richiede configurazione manuale, senza copiare le vecchie eccezioni')
    order=max(b['order']for m in manifests for b in m['ballots'])+1
    manifest=dict(schemaVersion=1,id=event_id,status='draft',ballots=[])
    for index, ballot in enumerate(template['ballots']):
        old=ballot['source']; prefix=old.get('chamber','europee')
        source={k:deepcopy(old[k])for k in ['title','category','columns','unit','level','chamber','resultKind'] if k in old}
        source.update(id=f'{prefix}-{year}',year=year,dateLabel=date_label,coverage='',note='',sourceURL='',downloadURL='',sourceFile='')
        if 'chamber' in source: source['eventID']=event_id
        manifest['ballots'].append(dict(order=order+index,source=source,seatsPolicy='pending' if 'chamber'in source else 'not-applicable'))
    ids={b['source']['id']for m in manifests for b in m['ballots']}
    require(not ids.intersection(b['source']['id']for b in manifest['ballots']),'ID scheda già usato: non sovrascrivere consultazioni dello stesso anno')
    return manifest
