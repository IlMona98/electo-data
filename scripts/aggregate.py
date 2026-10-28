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
    group, place, party, votes, electors, voters = config['columns']
    for row in rows:
        scope = row[group].strip()
        key = tuple(row[field].strip() for field in config['unit'])
        name = row[party].strip()
        count = int(row[votes])
        totals = (int(row[electors]), int(row[voters]))
        require(count >= 0 and 0 <= totals[1] <= totals[0], 'Invalid vote counts')
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
    item = {k:v for k,v in config.items() if k not in ['columns','unit','level','downloadURL','zipMember']}
    item.update(territories=records, sourceSHA256=hashlib.sha256(raw).hexdigest(), sourceUnits=len(units))
    return item
