"""Supplement Eligendo with explicit, dated institutional party/list tallies.
Never substitute a parliamentary group's size for an electoral list's seats.
"""
from collections import Counter, defaultdict
from hashlib import sha256
from io import BytesIO
import json
import re
from urllib.parse import urlencode, urlsplit
import urllib.request
from urllib.error import HTTPError, URLError
import time
from aggregate import require
from identities import normalize

CAMERA = 'https://dati.camera.it/sparql'
OSCE_2018 = 'https://cdn.osce.org/sites/default/files/f/documents/9/5/383589_1.pdf'
OSCE = 'https://cdn.osce.org/sites/default/files/f/documents/c/2/535974_1.pdf'


def camera_query(leg):
    require(type(leg) is int and 12 <= leg <= 19, 'Invalid parliamentary legislature')
    return f'''PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?member ?mandate ?start ?end ?date ?kind ?list ?coverage ?group ?groupLabel ?groupStart ?groupEnd WHERE {{
?member a ocd:deputato; ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_{leg}>; ocd:rif_mandatoCamera ?mandate.
?mandate ocd:startDate ?start; ocd:rif_elezione ?election. OPTIONAL {{?mandate ocd:endDate ?end}}
?election dc:date ?date; ocd:tipoElezione ?kind. OPTIONAL {{?election ocd:lista ?list}} OPTIONAL {{?election dc:coverage ?coverage}}
OPTIONAL {{?member ocd:aderisce ?membership. ?membership ocd:rif_gruppoParlamentare ?group; ocd:startDate ?groupStart; rdfs:label ?groupLabel. OPTIONAL {{?membership ocd:endDate ?groupEnd}}}}
}}'''


def camera_url(leg):
    return CAMERA + '?' + urlencode(dict(query=camera_query(leg), format='application/sparql-results+json'))


def official_url(url):
    p = urlsplit(url)
    require(p.scheme == 'https' and not p.username and not p.password and p.port in (None, 443) and not p.fragment,
            'Invalid supplementary source URL')
    if p.hostname == 'elezionistorico.interno.gov.it':
        from seats import official_page
        official_page(url); return
    require((p.hostname in ('dati.camera.it','dati.senato.it') and p.path == '/sparql') or url in (OSCE, OSCE_2018),
            'Unapproved supplementary source')


def download(url):
    official_url(url)
    if urlsplit(url).hostname == 'elezionistorico.interno.gov.it':
        from seats import download_page
        return download_page(url)
    request = urllib.request.Request(url, headers={'User-Agent': 'Electo/1.0 (+https://github.com/IlMona98/electo-data)'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                require(response.url == url and response.status == 200, 'Supplementary source redirected or unavailable')
                raw = response.read(12_000_001)
            require(len(raw) <= 12_000_000, 'Supplementary source too large')
            return raw
        except HTTPError as error:
            if attempt == 2 or error.code not in (500,502,503,504): raise
        except (URLError, TimeoutError, ConnectionError):
            if attempt == 2: raise
        time.sleep(attempt + 1)


def camera_members(raw, record):
    data = json.loads(raw)
    require(set(['member', 'mandate', 'start', 'date', 'kind']).issubset(data['head']['vars']), 'Missing parliamentary columns')
    members = defaultdict(list)
    for binding in data['results']['bindings']:
        row = {key: value['value'] for key, value in binding.items()}
        if row['start'] <= record['snapshot'] and row.get('end', '99999999') > record['snapshot'] and row['date'] == record['date']:
            require(row['member'].startswith(f'http://dati.camera.it/ocd/deputato.rdf/') and row['member'].endswith('_'+str(record['legislature'])), 'Wrong parliamentary member')
            members[row['member']].append(row)
    require(len(members) == record['expectedMembers'], 'Parliamentary cohort incomplete or includes later substitutions')
    result = []
    for member, rows in members.items():
        def unique(field, optional=False):
            values = {r[field] for r in rows if field in r}
            require(len(values) <= 1 and (optional or len(values) == 1), 'Ambiguous parliamentary election field: '+field)
            return next(iter(values), None)
        require(len({r['mandate'] for r in rows}) == 1, 'Duplicate parliamentary mandate')
        groups = {r['groupLabel'].split(' (')[0] for r in rows if r.get('groupStart', '99999999') <= record['snapshot'] and r.get('groupEnd', '99999999') > record['snapshot']}
        result.append(dict(member=member, kind=unique('kind'), name=unique('list', True), coverage=unique('coverage', True), groups=groups))
    return result


def list_counts(members, record):
    aliases = {normalize(k): v for k, v in record.get('aliases', {}).items()}
    outside = {normalize(n) for n in record.get('outsideLists', [])}
    counts = Counter(); parts = defaultdict(Counter); missing = 0
    for member in members:
        if member['name'] is None:
            require(member['kind'] == 'maggioritario', 'List missing in proportional mandate')
            missing += 1; continue
        name = aliases.get(normalize(member['name']), member['name'])
        if normalize(name) in outside: continue
        counts[normalize(name)] += 1
        abroad = normalize(member['coverage'] or '') in record['foreignAreas']
        parts[normalize(name)]['Estero' if abroad else 'Italia'] += 1
    require(missing == record['unlistedMembers'], 'Unexpected number of unlisted parliamentary mandates')
    return counts, parts


def osce_rows(text):
    """Read the six numeric cells, retaining names and the domestic/foreign boundary."""
    require('25 September 2022' in text and 'FINAL ELECTION RESULTS' in text and 'Total:' in text, 'Wrong institutional report')
    rows = {'Italia': {}, 'Estero': {}}; area = None
    number = r'(?:[\d,]+|-)'; pct = r'(?:\d+(?:\.\d+)?|-)'
    pattern = re.compile(r'^(.+?)\s+('+number+r')\s+('+pct+r')\s+(\d+|-)\s+('+number+r')\s+('+pct+r')\s+(\d+|-)\s*$')
    for line in text.splitlines():
        line = ' '.join(line.split())
        if 'Contestants (in-country constituencies)' in line: area = 'Italia'; continue
        if 'Contestants (out-of-country constituencies)' in line: area = 'Estero'; continue
        if not area: continue
        match = pattern.fullmatch(line)
        if not match: continue
        name, _, _, camera, _, _, senato = match.groups()
        require(name not in rows[area], 'Duplicate institutional party row')
        rows[area][name] = (int(camera) if camera != '-' else 0, int(senato) if senato != '-' else 0)
    # Two camera-only rows have blank Senate cells and must not disappear.
    require(re.search(r'Brambilla Michela Vittoria\s+43,244\s+1\s', text), 'Independent mandate missing')
    rows['Italia']['Brambilla Michela Vittoria'] = (1, 0)
    require(re.search(r'Autonomie progress f[eé]deralisme\s+20,763\s+38\.6\s+1\s', text), 'Aosta mandate missing')
    rows['Italia']['Vallée d’Aoste'] = (1, 0)
    require(sum(v[0] for area in rows.values() for v in area.values()) == 400 and sum(v[1] for area in rows.values() for v in area.values()) == 200,
            'Institutional report does not reconcile both chambers')
    return rows


def pdf_text(raw):
    from pypdf import PdfReader
    require(raw.startswith(b'%PDF-'), 'HTML instead of institutional PDF')
    reader = PdfReader(BytesIO(raw))
    require(len(reader.pages) == 27 and not reader.is_encrypted, 'Unexpected institutional report')
    require('13 January 2023' in ' '.join(reader.pages[0].extract_text().split()), 'Wrong institutional reference date')
    pages = [reader.pages[i] for i in (24, 25)]
    require(all(len(p.get_contents().get_data()) < 4_000_000 for p in pages), 'Oversized PDF content')
    return '\n'.join(p.extract_text() for p in pages)


def report_counts(rows, members, record):
    index = 0 if record['chamber'] == 'camera' else 1
    counts = Counter(); parts = defaultdict(Counter); ledger = Counter()
    aliases = record['aliases']
    for area, table in rows.items():
        for name, values in table.items():
            n = values[index]
            if name == 'The League-Brothers of Italy- Forza Italia' and n:
                require(record['chamber'] == 'camera' and area == 'Estero', 'Unexpected joint overseas list')
                joint = [m for m in members if m['name'] == record['jointForeignList']]
                require(len(joint) == n and all(len(m['groups']) == 1 for m in joint), 'Ambiguous joint overseas attribution')
                for member in joint:
                    group = next(iter(member['groups']))
                    require(group in record['foreignGroupAliases'], 'Unmapped initial overseas affiliation')
                    target = record['foreignGroupAliases'][group]
                    counts[normalize(target)] += 1; parts[normalize(target)]['Estero · appartenenza iniziale'] += 1
                ledger['Centrodestra'] += n; continue
            require(name in aliases, 'Unreviewed institutional row: '+name)
            target = aliases[name]
            if target:
                counts[normalize(target)] += n; parts[normalize(target)][area] += n
            if name in record['centreRightRows']: ledger['Centrodestra'] += n
    require(ledger['Centrodestra'] == record['expectedCentreRight'], 'Institutional coalition differs from Eligendo')
    return counts, parts


def apply_party_seats(elections, document, fetcher=download):
    require(document.get('schemaVersion') == 1 and isinstance(document.get('elections'), list), 'Invalid supplementary sources configuration')
    known = {e['id']: e for e in elections}; prepared = []; used = set(); cache = {}
    def get(url):
        if url not in cache: cache[url] = fetcher(url)
        return cache[url]
    for record in document['elections']:
        key = record['electionID']
        require(key in known and key not in used, 'Unknown or duplicate supplementary election'); used.add(key)
        election = known[key]
        require(election['chamber'] == record['chamber'] and election['seats']['totalSeats'] == record['totalSeats'], 'Wrong supplementary chamber')
        require(int(record['referenceDate'][:4]) >= election['year'], 'Supplementary reference predates election')
        if record['chamber'] == 'camera':
            require(record['expectedMembers'] == record['totalSeats'] and int(record['date'][:4]) == election['year'], 'Wrong supplementary parliamentary cohort')
        sources = []; members = []; reconciliation = None
        if record['adapter'] == 'camera-lists' or record['chamber'] == 'camera':
            url = camera_url(record['legislature']); raw = get(url); members = camera_members(raw, record)
            sources.append(dict(label='Camera dei deputati · dati elettorali storici', url=url, sha256=sha256(raw).hexdigest()))
        if record['adapter'] == 'camera-lists':
            counts, parts = list_counts(members, record)
        elif record['adapter'] == 'reconciled-2018':
            from reconcile_2018 import reconcile, senato_url, senato_members
            if record['chamber'] == 'senato':
                url = senato_url(); raw = get(url)
                members = senato_members(raw,record['snapshot'],record['expectedMembers'])
                sources.append(dict(label='Senato · mandati e prime appartenenze',url=url,sha256=sha256(raw).hexdigest()))
            raw=get(OSCE_2018)
            counts,parts,reconciliation,ministerial=reconcile(election,record,raw,members,get)
            sources.append(dict(label='OSCE/ODIHR · allegato 2018 riconciliato',url=OSCE_2018,sha256=sha256(raw).hexdigest()))
        else:
            require(record['adapter'] == 'osce-2022', 'Unknown supplementary adapter')
            raw = get(OSCE); counts, parts = report_counts(osce_rows(pdf_text(raw)), members, record)
            sources.append(dict(label='OSCE/ODIHR · risultati 2022, pp. 23–24', url=OSCE, sha256=sha256(raw).hexdigest()))
        national = election['territories'][0]['results']; names = {normalize(r['name']): r for r in national}
        require(not(set(counts)-set(names)-{normalize(n) for n in record.get('outsideLists', [])}), 'Parliamentary list needs a reviewed alias')
        totals = []
        for name, n in counts.items():
            if name not in names: continue
            row = names[name]
            require(0 <= n <= record['totalSeats'] and n >= row.get('listSeats', 0), 'Supplementary total below verified proportional seats')
            components = [dict(label=label,seats=value) for label,value in parts[name].items() if value]
            require(sum(p['seats'] for p in components) == n, 'Supplementary components do not reconcile')
            totals.append(dict(resultID=row['id'], name=row['name'], seats=n, components=components,
                               sourcePages=sources, note=record['note'], referenceDate=record['referenceDate']))
        require(totals, 'No verified supplementary totals')
        prepared.append((election, totals, reconciliation))
    # No publication is mutated until every configured source passes.
    for election, totals, reconciliation in prepared:
        election['seats']['partyTotals'] = totals
        if reconciliation is not None:
            election['seats']['partyReconciliation'] = reconciliation
            if election['id']=='senato-2018': election['seats']['unassignedLabel']='Non assegnato · Sicilia'
    return elections
