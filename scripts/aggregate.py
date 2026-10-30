import collections, csv, hashlib, io

def require(condition, message):
    if not condition:
        raise ValueError(message)

def decode(raw):
    try: return raw.decode('utf-8-sig')
    except UnicodeDecodeError: return raw.decode('cp1252')

def slug(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def build(raw, config):
    rows = csv.DictReader(io.StringIO(decode(raw)), delimiter=';')
    units, seen, territories = {}, set(), {}
    reviewed = {tuple(item["unit"]): item for item in config.get("reviewedTurnoutExceptions", [])}
    quality_notes = set()
    group, place, party, votes, electors, voters = config['columns']
    for row in rows:
        scope = row[group].strip()
        key = tuple(row[field].strip() for field in config['unit'])
        name = row[party].strip()
        count = int(row[votes])
        totals = (int(row[electors]), int(row[voters]))
        exception = reviewed.get(key)
        matches_reviewed = exception is not None and totals == (exception['electors'], exception['voters'])
        require(count >= 0 and totals[0] >= 0 and totals[1] >= 0 and (totals[1] <= totals[0] or matches_reviewed), 'Invalid vote counts')
        if totals[1] > totals[0]:
            quality_notes.add(exception['reason'])
        require((key, name) not in seen, 'Duplicate list/territory row')
        seen.add((key,name))
        if key in units:
            require(units[key] == totals, 'Conflicting elector or voter counts')
        else:
            units[key] = totals
            for tid, title, level in [('italia', 'Italia', 'Nazionale'), (slug(scope), scope, config['level'])]:
                target = territories.setdefault(tid, dict(id=tid, name=title, level=level, electors=0, voters=0, lists=collections.Counter()))
                target['electors'] += totals[0]
                target['voters'] += totals[1]
        territories['italia']['lists'][name] += count
        territories[slug(scope)]['lists'][name] += count
    records = []
    for target in sorted(territories.values(), key=lambda t:(t['id'] != 'italia',t['name'])):
        target['results'] = [dict(id=slug(name),name=name,votes=count) for name,count in sorted(target.pop('lists').items(),key=lambda x:(-x[1],x[0]))]
        require(sum(x['votes'] for x in target['results']) <= target['voters'], 'Votes exceed voters')
        records.append(target)
    require(len(records) > 1 and records[0]['id'] == 'italia', 'Empty or incomplete source')
    # Every domestic aggregate is the exact sum of its territorial components.
    for field in ['electors','voters']:
        require(records and records[0][field] == sum(t[field] for t in records[1:]), 'National totals disagree with territories')
    item = {k:v for k,v in config.items() if k not in ['columns','unit','level','downloadURL','zipMember','reviewedTurnoutExceptions']}
    if quality_notes:
        item['qualityNotes'] = sorted(quality_notes)
        item['note'] += ' ' + ' '.join(sorted(quality_notes))
    for key in ['eventID','chamber']:
        if config.get(key) is not None: item[key] = config[key]
    item.update(territories=records, sourceSHA256=hashlib.sha256(raw).hexdigest(), sourceUnits=len(units))
    return item


def count(value):
    """Ministry tables use exact integer counts serialized as e.g. 12345,00."""
    import re
    text = value.strip()
    require(re.fullmatch(r'[0-9]+(?:,0+)?', text) is not None, 'Non-integer or invalid count')
    return int(text.split(',')[0])


def public_metadata(config):
    keys = ['id','title','category','year','dateLabel','coverage','note','sourceURL','sourceFile']
    return {key: config[key] for key in keys} | {key: config[key] for key in ['eventID','chamber','previousElectionID','comparisonTerritories','comparisonAliases'] if key in config}


def build_tables(members, config):
    """Join published territorial totals/lists and reconcile against national tables."""
    mapping = config['tables']
    def rows(key):
        return list(csv.DictReader(io.StringIO(decode(members[mapping[key]])), delimiter=';'))
    stats = rows('stats')
    lists = rows('lists')
    national_stats = rows('nationalStats')
    national_lists = rows('nationalLists')
    require(len(national_stats)==1 and len(stats)>1 and lists and national_lists, 'Incomplete aggregate tables')
    stats_key = mapping['statsKey']
    lists_key = mapping['listsKey']
    territories = {}
    for row in stats:
        name = row[stats_key].strip()
        require(name and name not in territories, 'Duplicate or missing territorial total')
        electors, voters, valid = (count(row[k]) for k in ['NUMELETTORITOTALI','NUMVOTANTITOTALI','VOTIVALIDILISTE'])
        require(0 <= valid <= voters <= electors and electors > 0, 'Invalid scrutiny counts')
        territories[name] = dict(id=slug(name),name=name,level=config['level'],electors=electors,voters=voters,lists=collections.Counter(),expected=valid)
    seen = set()
    for row in lists:
        territory, party = row[lists_key].strip(), row['LISTA'].strip()
        require(territory in territories and party, 'List outside scrutiny geography')
        require((territory,party) not in seen, 'Duplicate territorial list')
        seen.add((territory,party))
        territories[territory]['lists'][party] = count(row['VOTILISTA'])
    total_lists = collections.Counter()
    for territory in territories.values():
        require(sum(territory['lists'].values())==territory.pop('expected'), 'List votes disagree with territorial scrutiny')
        # Counter.update preserves counts including zeros without discarding identities.
        total_lists.update(territory['lists'])
    expected_lists = {}
    for row in national_lists:
        party = row['LISTA'].strip()
        require(party and party not in expected_lists,'Duplicate national list')
        expected_lists[party] = count(row['VOTILISTA'])
    require(dict(total_lists)==expected_lists,'National and territorial list counts disagree')
    national = national_stats[0]
    electors, voters, valid = (count(national[k]) for k in ['NUMELETTORITOTALI','NUMVOTANTITOTALI','VOTIVALIDILISTE'])
    require(sum(t['electors'] for t in territories.values())==electors and sum(t['voters'] for t in territories.values())==voters, 'National and territorial turnout disagree')
    require(sum(expected_lists.values())==valid and 0<=valid<=voters<=electors, 'National valid votes disagree')
    records = [dict(id='italia',name='Italia',level='Nazionale',electors=electors,voters=voters,lists=total_lists)] + sorted(territories.values(),key=lambda t:t['name'])
    for territory in records:
        territory['results'] = [dict(id=slug(name),name=name,votes=votes) for name,votes in sorted(territory.pop('lists').items(),key=lambda x:(-x[1],x[0]))]
    hasher = hashlib.sha256()
    for name in sorted(members):
        raw = members[name]
        hasher.update(name.encode()+b'\0'+str(len(raw)).encode()+b'\0'+raw)
    return public_metadata(config) | dict(territories=records,sourceFiles=sorted(members),sourceSHA256=hasher.hexdigest(),sourceUnits=len(territories))
