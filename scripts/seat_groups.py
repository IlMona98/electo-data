"""Consolidate the same electoral coalition/list across ballot components.
Original groups are retained for audit and for result rows with a narrower scope.
"""
from collections import Counter
from copy import deepcopy
from aggregate import require
from identities import normalize

MERGE_NOTE = "Le voci del grafico accorpano le componenti della stessa coalizione/lista. I dati originari restano conservati separatamente per verificare quote e perimetri."


def consolidate_seats(elections, document):
    require(document.get('schemaVersion') == 1 and isinstance(document.get('elections'), list), 'Invalid seat consolidation configuration')
    definitions = {r['electionID']: r for r in document['elections']}
    require(len(definitions) == len(document['elections']) and set(definitions).issubset({e['id'] for e in elections}), 'Unknown or duplicate seat consolidation election')
    prepared = []
    for election in elections:
        if 'seats' not in election: continue
        allocation = election['seats']
        original = deepcopy(allocation.get('originalGroups', allocation['groups']))
        raw = {g['id']:g for g in original}
        names = {normalize(g['name']) for g in original}
        results = {r['id']:r for r in election['territories'][0]['results']}
        record = definitions.get(election['id'], {})
        targets = {}; explicit = {}
        for definition in record.get('groups', []):
            require(definition['id'] not in targets and definition['name'] and definition['members'], 'Duplicate or empty consolidated group')
            targets[definition['id']] = definition
            for name in definition['members']:
                key = normalize(name)
                require(key in names and key not in explicit, 'Unreviewed or ambiguous original seat group: '+name)
                explicit[key] = definition['id']
        assignments = {}; identity_targets = {}
        for group in original:
            key = normalize(group['name'])
            if key in explicit:
                target = explicit[key]
            else:
                row = results.get(group.get('resultID'))
                coalition = row.get('coalitionID') if row else None
                target = coalition if coalition in raw else identity_targets.get(key, group['id'])
            assignments[group['id']] = target
            identity_targets.setdefault(key, target)
        # Resolve party -> coalition links after any explicit consolidation of that coalition.
        for key in assignments:
            seen = set(); target = assignments[key]
            while target in assignments and assignments[target] != target:
                require(target not in seen, 'Cyclic seat consolidation'); seen.add(target); target = assignments[target]
            assignments[key] = target
        grouped = {}; parts = {}
        for group in original:
            target = assignments[group['id']]
            if target not in grouped:
                base = deepcopy(raw.get(target, group))
                if target in targets:
                    base['id'] = target; base['name'] = targets[target]['name']
                    base.pop('resultID',None);base.pop('entityID',None)
                base['seats'] = 0; base.pop('components',None)
                grouped[target] = base; parts[target] = Counter()
            grouped[target]['seats'] += group['seats']
            components = group.get('components') or [dict(label=group.get('detail') or 'Riparto ministeriale',seats=group['seats'])]
            for part in components: parts[target][part['label']] += part['seats']
        for key, group in grouped.items():
            if sum(assignments[g['id']] == key for g in original) > 1 or key in targets: group.pop('detail',None)
            group['components'] = [dict(label=label,seats=n) for label,n in parts[key].items() if n]
            require(sum(p['seats']for p in group['components']) == group['seats'], 'Consolidated components do not reconcile')
        require(sum(g['seats']for g in grouped.values()) == sum(g['seats']for g in original), 'Consolidation changed the seat total')
        value = deepcopy(allocation)
        value['originalGroups'] = original
        value['groups'] = list(grouped.values())
        value['note'] = allocation['note'].split('\n\n'+MERGE_NOTE,1)[0].replace('distinto per componenti e perimetri indicati in legenda.', 'comprensivo delle componenti e dei perimetri ministeriali.') + '\n\n'+MERGE_NOTE
        if record.get('note'): value['note'] += '\n'+record['note']
        prepared.append((election,value))
    for election,value in prepared:election['seats']=value
    return elections
