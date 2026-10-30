"""Read seat counts from Eligendo's archive tables; never derive seats from votes."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit, parse_qs
import urllib.request
from urllib.error import HTTPError, URLError
import time
from aggregate import require
from identities import normalize

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Electo/1.0; +https://github.com/IlMona98/electo-data)',
           'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'it-IT,it;q=0.9'}
MAX_PAGE = 2_000_000


def official_page(url):
    p = urlsplit(url)
    require(p.scheme == 'https' and p.hostname == 'elezionistorico.interno.gov.it'
            and p.port in (None,443) and p.path == '/index.php'
            and not p.username and not p.password and not p.fragment, 'Invalid seat source URL')
    q = parse_qs(p.query, strict_parsing=True)
    require(all(len(v)==1 for v in q.values()) and q.get('tpel',[None])[0] in ('C','S')
            and re.fullmatch(r'\d{2}/\d{2}/\d{4}',q.get('dtel',[''])[0]), 'Invalid seat source parameters')
    return q


class SeatRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        official_page(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_page(url):
    official_page(url)
    request = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(3):
        try:
            with urllib.request.build_opener(SeatRedirect()).open(request, timeout=45) as response:
                require(response.url == url and response.status == 200, 'Seat source redirected or unavailable')
                raw = response.read(MAX_PAGE+1)
                require(len(raw)<=MAX_PAGE, 'Seat source too large')
                return raw
        except HTTPError as error:
            if attempt==2 or error.code not in (500,502,503,504):raise
        except (URLError,TimeoutError,ConnectionError):
            if attempt==2:raise
        time.sleep(attempt+1)


class SeatTable(HTMLParser):
    """Use semantic cell identifiers, not column offsets or visual ordering."""
    def __init__(self):
        super().__init__(); self.tables=0; self.inside=False; self.heading=False
        self.headings=[]; self.title=''; self.rows=[]; self.row=None; self.cell=None
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='h3': self.heading=True; self.title=''
        if tag=='table':
            self.inside=attrs.get('summary') in ('Risultato elezione','Risultati elezione')
            if self.inside: self.tables+=1
        if self.inside:
            if tag=='tr': self.row=[]
            if tag in ('td','th'): self.cell=[attrs,'']
    def handle_data(self, text):
        if self.heading: self.title+=text
        if self.cell is not None: self.cell[1]+=text
    def handle_endtag(self, tag):
        if tag=='h3' and self.heading:
            self.headings.append(' '.join(self.title.split())); self.heading=False
        if tag in ('td','th') and self.cell is not None:
            require(self.row is not None, 'Seat cell outside row')
            self.cell[1]=' '.join(self.cell[1].split()); self.row.append(self.cell); self.cell=None
        if tag=='tr' and self.inside and self.row is not None:
            self.rows.append(self.row); self.row=None
        if tag=='table': self.inside=False


def count(text):
    require(bool(re.fullmatch(r'\d{1,4}',text)), 'Invalid ministerial seat count')
    return int(text)


def cell_count(row):
    cells=[v for a,v in row if 'hseggi' in a.get('headers','').split()]
    require(len(cells)<=1, 'Duplicate seat cell')
    return count(cells[0]) if cells and cells[0] else 0


def parse_page(raw, source):
    require(len(raw)<=MAX_PAGE, 'Seat source too large')
    p=SeatTable(); p.feed(raw.decode('utf-8-sig'))
    require(p.tables==1 and source['heading'] in p.headings, 'Wrong election, area or missing results table')
    kind=source['kind']; blocks=[]; seen=set(); declared=[]; current=None; current_key=None
    require(kind in ('italia','estero','valledaosta','uninominale'), 'Unknown seat area')
    if kind not in ('valledaosta','uninominale'):
        require(any(a.get('id')=='hseggi' and v=='Seggi' for row in p.rows for a,v in row), 'Missing seat column')
    for row in p.rows:
        candidates=[(a['id'],v) for a,v in row if re.fullmatch(r'candidato\d+',a.get('id',''))]
        lists=[(a['id'],v) for a,v in row if re.fullmatch(r'lista\d+(?:_\d+)?',a.get('id',''))]
        if candidates:
            key,name=candidates[0]
            require(len(candidates)==1 and key not in seen, 'Duplicate candidate block'); seen.add(key)
            current_key=key
            if kind in ('valledaosta','uninominale'):
                current={'seats': int(any(v=='Eletto' for a,v in row)), 'lists':[]}
            else:
                require(kind=='italia' and name=='CANDIDATI UNINOMINALI', 'Unexpected candidate row')
                current={'seats':cell_count(row), 'lists':[]}
            blocks.append(current)
        elif lists:
            key,name=lists[0]
            require(len(lists)==1 and key not in seen and name, 'Duplicate or empty list'); seen.add(key)
            if kind=='estero':
                require(any('hseggi' in a.get('headers','').split() for a,v in row), 'Missing foreign list seats')
                blocks.append({'seats':cell_count(row), 'lists':[name]})
            else:
                require(kind=='italia' and current is not None, 'List without candidate block')
                require(any(a.get('id')==key and current_key in a.get('headers','').split() for a,v in row), 'List belongs to another candidate block')
                current['lists'].append(name); current['seats']+=cell_count(row)
        elif kind in ('valledaosta','uninominale'):
            names=[v for a,v in row if 'hlista' in a.get('headers','').split()]
            if names:
                require(current is not None and all(names), 'Unlinked special college list')
                require(all(current_key in a.get('headers','').split() for a,v in row if 'hlista' in a.get('headers','').split()), 'Special college list belongs to another candidate')
                current['lists'].extend(names)
        if any('hseggi' in a.get('headers','').split() and 'htotalecomplessivo' in a.get('headers','') for a,v in row):
            declared.append(cell_count(row))
    require(blocks and all(b['lists'] for b in blocks), 'Missing linked lists')
    if kind in ('valledaosta','uninominale'): require(sum(b['seats'] for b in blocks)==1, 'Special college elected candidate not declared')
    else:
        require(len(declared)==(2 if kind=='italia' else 1), 'Missing ministerial seat totals')
        require(sum(b['seats'] for b in blocks)==sum(declared), 'Ministerial rows do not reconcile with totals')
    return [b for b in blocks if b['seats']>0]


def allocation(record, fetcher=download_page):
    sources=record['sources']
    special=record.get('specialCollegeCount',0)
    require(type(special) is int and 0<=special<=6, 'Invalid special college count')
    expected=Counter(italia=1,estero=1,valledaosta=1)
    if special: expected['uninominale']=special
    require(Counter(s['kind'] for s in sources)==expected and len({s['url'] for s in sources})==len(sources), 'Incomplete seat coverage')
    definitions={g['id']:g for g in record['groups']}; aliases={}
    require(len(definitions)==len(record['groups']), 'Duplicate seat group definitions')
    for g in definitions.values():
        require(g['id'] and g['name'] and g['aliases'], 'Missing seat identity')
        for alias in g['aliases']:
            key=normalize(alias)
            require(key not in aliases, 'Ambiguous seat membership'); aliases[key]=g['id']
    counts=Counter(); provenance=[]; list_results={}
    for source in sources:
        params=official_page(source['url'])
        require(params['tpel']==[record['type']] and params['dtel']==[record['date']], 'Seat URL belongs to another election')
        expected_area={'italia':'I','estero':'E','valledaosta':'H' if record['type']=='C' else 'G','uninominale':'G'}[source['kind']]
        require(params.get('tpa')==[expected_area], 'Wrong seat area URL')
        if source['kind']=='uninominale':
            require(record['type']=='S' and params.get('lev0')==['4'] and params.get('tpe')==['L'], 'Wrong special college')
        raw=fetcher(source['url'])
        for block in parse_page(raw,source):
            # Every linked list must map to the same group; coalition wins cannot be attributed to its largest party.
            resolved={aliases.get(normalize(n)) for n in block['lists']}
            require(len(resolved)==1 and None not in resolved, 'Unconfigured or mixed seat coalition: '+repr(block['lists']))
            counts[resolved.pop()]+=block['seats']
        if source['kind']=='italia':
            table=SeatTable(); table.feed(raw.decode('utf-8-sig'))
            linked={}
            for row in table.rows:
                for attrs,name in row:
                    if re.fullmatch(r'lista\d+_\d+',attrs.get('id','')):
                        parent=next(k for k in attrs['headers'].split() if k.startswith('candidato'))
                        linked.setdefault(parent,[]).append((name,cell_count(row)))
            for members in linked.values():
                resolved={aliases.get(normalize(name)) for name,seats in members}
                coalition=next(iter(resolved)) if len(members)>1 and len(resolved)==1 and None not in resolved else None
                for name,seats in members:
                    detail=dict(listSeats=seats)
                    if coalition: detail.update(coalitionID=coalition,coalitionName=definitions[coalition]['name'])
                    require(normalize(name) not in list_results,'Duplicate list seat metadata')
                    list_results[normalize(name)]=detail
        provenance.append(dict(label=source['label'],url=source['url'],sha256=sha256(raw).hexdigest()))
    require(sum(counts.values())+record['unreportedSeats']==record['totalSeats'], 'Incomplete parliamentary seat allocation')
    return dict(chamber=record['chamber'],totalSeats=record['totalSeats'],unassignedSeats=record['unreportedSeats'],
                groups=[dict(id=g['id'],name=g['name'],seats=counts[g['id']]) for g in record['groups'] if counts[g['id']]],
                sourceURL=sources[0]['url'],sourceLabel='Eligendo · Archivio',sourcePages=provenance,unassignedLabel='Non riportati dalla fonte',listResults=list_results,
                checkedAt=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                coverage=('Intera Camera' if record['chamber']=='camera' else 'Senato elettivo')+' · Italia ed estero',
                note='Seggi uninominali e di lista pubblicati da Eligendo, aggregati per coalizione/lista. Comprende Italia, Valle d’Aosta ed estero; non indica i gruppi parlamentari attuali. Il territorio selezionato non modifica il riepilogo.'
                + (f" La fonte riporta {record['totalSeats']-record['unreportedSeats']} dei {record['totalSeats']} seggi elettivi; i seggi non riportati sono rappresentati vuoti." if record['unreportedSeats'] else '')
                + (' Comprende i sei collegi uninominali del Trentino-Alto Adige.' if special else '')
                + (' Senatori a vita esclusi.' if record['chamber']=='senato' else ''))


def apply_seats(elections, document, fetcher=download_page):
    require(document.get('schemaVersion')==2 and isinstance(document.get('elections'),list), 'Invalid seat sources configuration')
    known={e['id']:e for e in elections}; seen=set(); prepared=[]
    for record in document['elections']:
        key=record['electionID']
        require(key in known and key not in seen, 'Unknown or duplicate seat election'); seen.add(key)
        require(record['chamber']==known[key].get('chamber') and record['type']=={'camera':'C','senato':'S'}.get(record['chamber']), 'Wrong seat chamber')
        require(type(record['totalSeats']) is int and 1<=record['totalSeats']<=1000 and type(record['unreportedSeats']) is int and 0<=record['unreportedSeats']<record['totalSeats'], 'Invalid chamber capacity')
        if record.get('adapter')=='historical-pages':
            from historical_seats import allocation as historical_allocation
            value=historical_allocation(record,fetcher)
        else:
            value=allocation(record,fetcher)
        details=value.pop('listResults')
        names={normalize(r['name']):r['id'] for r in known[key]['territories'][0]['results']}
        for group in value['groups']:
            if normalize(group['name']) in names: group['resultID']=names[normalize(group['name'])]
        prepared.append((known[key],value,details))
    # Do not mutate any election until every page has passed reconciliation.
    for election,value,details in prepared:
        election['seats']=value
        for territory in election['territories']:
            for result in territory['results']:
                detail=details.get(normalize(result['name']))
                if detail:
                    for field in ('coalitionID','coalitionName'):
                        if field in detail: result[field]=detail[field]
                    if territory.get('id')=='italia': result['listSeats']=detail['listSeats']
    return elections
