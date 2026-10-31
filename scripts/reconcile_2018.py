"""Resolve the 2018 report's mislabeled rows against ministerial vote identities."""
from collections import Counter, defaultdict
from hashlib import sha256
from io import BytesIO
import json
import re
from urllib.parse import urlencode
from aggregate import require
from identities import normalize
from seats import SeatTable, parse_page


def senato_url(leg=18):
    require(leg == 18, 'Unreviewed Senate legislature')
    query='''PREFIX osr: <http://dati.senato.it/osr/> PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT DISTINCT ?member ?start ?end ?type ?region ?group ?groupStart ?groupEnd WHERE {
?member a osr:Senatore; osr:mandato ?mandate. ?mandate osr:legislatura 18; osr:tipoMandato ?type; osr:inizio ?start.
OPTIONAL {?mandate osr:fine ?end} OPTIONAL {?mandate osr:regioneElezione ?region}
OPTIONAL {?member ocd:aderisce ?membership. ?membership osr:legislatura 18; osr:gruppo ?group; osr:inizio ?groupStart. OPTIONAL {?membership osr:fine ?groupEnd}}
}'''
    return 'https://dati.senato.it/sparql?'+urlencode(dict(query=query,format='application/sparql-results+json'))


def senato_members(raw, snapshot, expected):
    rows=json.loads(raw)['results']['bindings'];members=defaultdict(list)
    date=snapshot[:4]+'-'+snapshot[4:6]+'-'+snapshot[6:]
    for b in rows:
        r={k:v['value']for k,v in b.items()}
        if r['type']=='elettivo' and r['start']<=date and r.get('end','9999')>date:members[r['member']].append(r)
    require(len(members)==expected,'Incomplete initial Senate cohort')
    result=[]
    foreign={'EUROPA','AMERICA MERIDIONALE','AMERICA SETTENTRIONALE E CENTRALE','AFRICA ASIA OCEANIA ANTARTIDE'}
    for uri,rs in members.items():
        require(uri.startswith('http://dati.senato.it/senatore/'),'Unexpected Senate member URI')
        regions={r.get('region')for r in rs};require(len(regions)==1,'Ambiguous Senate electoral region')
        groups={r['group']for r in rs if r.get('groupStart','9999')<=date and r.get('groupEnd','9999')>date}
        if next(iter(regions)) in foreign:
            require(len(groups)==1,'Ambiguous initial foreign Senate affiliation')
        result.append(dict(member=uri,foreign=next(iter(regions))in foreign,groups=groups))
    return result


def report_rows(text,chamber):
    require(chamber in ('camera','senato'),'Unknown 2018 chamber')
    require('4 March 2018'in text and 'OFFICIAL ELECTION RESULTS'in text,'Wrong 2018 report annex')
    camera,senate=text.split('Chamber of Deputies',1)[1].split('Senate',1)
    section=camera if chamber=='camera'else senate.split('47  Sources:',1)[0]
    rows=[]
    for match in re.finditer(r'^\s*(\d+)\s+(.+?)\s+([\d,]+)\s+(\d+)\s*$',section,re.M):
        rank,name,votes,seats=match.groups()
        if name=='Five Star Movement'and seats=='11248':
            require(chamber=='senato'and 'One seat won by the Five Star Movement in Sicily has remained unassigned'in text,'Missing vacancy footnote')
            seats='112'
        rows.append(dict(rank=int(rank),reportedName=name,votes=int(votes.replace(',','')),seats=int(seats)))
    require(len(rows)==11 and {r['rank']for r in rows}==set(range(1,12)),'Incomplete 2018 report table')
    require(sum(r['seats']for r in rows)==(617 if chamber=='camera'else 308),'2018 report seat rows do not reconcile')
    return rows


def vote_rows(raw,source):
    parse_page(raw,source) # validates date, area, totals and linked lists before reading votes
    p=SeatTable();p.feed(raw.decode('utf-8-sig'));rows=[]
    for row in p.rows:
        names=[v for a,v in row if re.fullmatch(r'lista\d+_\d+',a.get('id',''))]
        if not names:continue
        votes=[v for a,v in row if 'hvoti'in a.get('headers','').split()]
        require(len(names)==len(votes)==1 and re.fullmatch(r'\d+(?:\.\d{3})*',votes[0]),'Ministerial list vote cell missing')
        rows.append(dict(name=names[0],votes=int(votes[0].replace('.',''))))
    require(rows and len({normalize(r['name'])for r in rows})==len(rows),'Duplicate ministerial voting identity')
    return rows


def align_rows(reported,ministerial,reviewed):
    used=set();aligned=[];audit=[]
    # Names are reviewed explicitly: nearby vote totals alone never assign a party.
    # The vote check allows the documented differences between report and archive;
    # the independent coalition ledger below must still reconcile exactly.
    for row in reported:
        require(row['reportedName'] in reviewed, 'Unreviewed report label')
        target=normalize(reviewed[row['reportedName']])
        matches=[m for m in ministerial if normalize(m['name'])==target and m['votes']>0 and abs(m['votes']-row['votes'])/m['votes']<=0.035]
        require(len(matches)==1,'Report voting identity cannot be unambiguously reconciled')
        match=matches[0];key=normalize(match['name']);require(key not in used,'Report maps two rows to one list');used.add(key)
        aligned.append(dict(name=match['name'],seats=row['seats'],reportedName=row['reportedName']))
        audit.append(dict(reportedName=row['reportedName'],ministerialName=match['name'],reportedVotes=row['votes'],ministerialVotes=match['votes']))
    return aligned,audit


def reconcile(election,record,pdf_raw,members,fetcher):
    from pypdf import PdfReader
    require(pdf_raw.startswith(b'%PDF-'),'HTML instead of institutional PDF')
    reader=PdfReader(BytesIO(pdf_raw));require(len(reader.pages)==24 and not reader.is_encrypted,'Wrong 2018 report')
    require(len(reader.pages[22].get_contents().get_data())<4_000_000,'Oversized institutional PDF content')
    require('6 June 2018'in ' '.join(reader.pages[0].extract_text().split()),'Wrong report reference date')
    text=reader.pages[22].extract_text();reported=report_rows(text,record['chamber'])
    primary=next(s for s in record['ministerialSources']if s['kind']=='italia')
    raw=fetcher(primary['url']);mapped,audit=align_rows(reported,vote_rows(raw,primary),record['reviewedReportNames'])
    national=election['territories'][0]['results'];by_name={normalize(r['name']):r for r in national}
    group_of={}
    for group in record['ministerialGroups']:
        for name in group['aliases']:
            key=normalize(name)
            require(key not in group_of or group_of[key]==group['id'],'Ambiguous reviewed coalition alias')
            group_of[key]=group['id']
    counts=Counter();parts=defaultdict(Counter);ledger=Counter();outside=[]
    for row in mapped:
        name=normalize(row['name']);n=row['seats']
        if row['reportedName']=='Five Star Movement'and record['chamber']=='senato':
            require(election['seats']['unassignedSeats']==1,'Unreviewed Sicilian vacancy');n-=1
        require(name in by_name and name in group_of,'Unmapped national 2018 winner')
        counts[name]+=n;parts[name]['Italia · riscontro riconciliato']+=n;ledger[group_of[name]]+=n
    sources=[dict(label=primary['label'],url=primary['url'],sha256=sha256(raw).hexdigest())]
    for source in record['ministerialSources']:
        if source['kind']=='italia':continue
        raw=fetcher(source['url']);blocks=parse_page(raw,source)
        sources.append(dict(label=source['label'],url=source['url'],sha256=sha256(raw).hexdigest()))
        for block in blocks:
            require(len(block['lists'])==1,'Unreviewed 2018 foreign or special block')
            name=block['lists'][0];key=normalize(name);n=block['seats']
            require(key in group_of,'Unmapped foreign/special coalition')
            ledger[group_of[key]]+=n
            if source['kind']=='estero'and key==normalize(record['jointForeignList']):
                if record['chamber']=='camera':selected=[m for m in members if m['name']==record['parliamentaryJointList']]
                else:selected=[m for m in members if m['foreign']and next(iter(m['groups']))in record['foreignGroupAliases']]
                require(len(selected)==n and all(len(m['groups'])==1 for m in selected),'Joint foreign attribution incomplete')
                for m in selected:
                    group=next(iter(m['groups']));require(group in record['foreignGroupAliases'],'Unreviewed foreign affiliation')
                    target=normalize(record['foreignGroupAliases'][group]);require(target in by_name,'Unknown overseas party')
                    counts[target]+=1;parts[target]['Estero · attribuzione iniziale']+=1
            elif key in by_name:
                counts[key]+=n;parts[key]['Estero'if source['kind']=='estero'else'Collegio speciale']+=n
            else:outside.append(dict(name=name,seats=n,groupID=group_of[key]))
    expected=Counter({g['id']:g['seats']for g in election['seats'].get('originalGroups',election['seats']['groups'])})
    require(ledger==expected,'Reconciled 2018 parties disagree with ministerial coalitions')
    require(sum(counts.values())+sum(g['seats']for g in outside)==sum(expected.values()),'2018 reconciliation lost or duplicated mandates')
    # The closed, fully reconciled tally also verifies absence of mandates, not just winners.
    for row in national:counts.setdefault(normalize(row['name']),0)
    return counts,parts,dict(voteIdentityChecks=audit,outsideBallot=outside,groupTotals=dict(ledger),sourcePages=sources),sources
