"""Historical Eligendo seat tables and explicitly elected single-member colleges."""
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from html.parser import HTMLParser
from hashlib import sha256
from datetime import datetime,timezone
import re
from urllib.parse import urljoin,urlsplit,parse_qs
from aggregate import require
from identities import normalize
from seats import SeatTable,cell_count,official_page,download_page

class HistoricalTable(SeatTable):
    def __init__(self):
        super().__init__();self.annotation=False
    def handle_starttag(self,tag,attrs):
        if tag=='span' and self.cell is not None and 'fontpiccolo' in dict(attrs).get('class','').split():
            self.annotation=True;self.cell[0]['annotation']='';return
        super().handle_starttag(tag,attrs)
    def handle_data(self,text):
        if self.annotation and self.cell is not None:self.cell[0]['annotation']+=text
        else:super().handle_data(text)
    def handle_endtag(self,tag):
        if tag=='span' and self.annotation:self.annotation=False;return
        super().handle_endtag(tag)

class Selects(HTMLParser):
    def __init__(self):
        super().__init__();self.items=[];self.current=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='select':self.current=dict(attrs=attrs,options=[]);self.items.append(self.current)
        elif tag=='option' and self.current is not None:self.current['options'].append(attrs)
    def handle_endtag(self,tag):
        if tag=='select':self.current=None


def child_pages(raw,url):
    p=Selects();p.feed(raw.decode('utf-8-sig'));q=parse_qs(urlsplit(url).query)
    for select in p.items:
        attrs=select['attrs'];match=re.search(r"carica_pagina\('([^']+)','(ne\d+)'",attrs.get('onchange',''))
        if 'disabled' in attrs or not match:continue
        base,param=match.groups()
        if param in q:continue
        options=[o['value'] for o in select['options'] if re.fullmatch(r'\d+(?:-lev\d+)+',o.get('value',''))]
        if not options:continue
        result=[]
        for value in options:
            code,*tail=value.split('-');suffix='&'.join(re.sub(r'^(lev\d)',r'\1=',v) for v in tail)
            child=urljoin(url,base)+'&'+param+'='+code+'&'+suffix
            if q.get('unipro')==['uni']:child+='&unipro=uni'
            official_page(child);result.append(child)
        return result
    return []


def read_table(raw,record,source,url):
    table=HistoricalTable();table.feed(raw.decode('utf-8-sig'))
    if not table.tables:return None
    require(table.tables==1 and any(h.startswith(record['headingPrefix']) for h in table.headings),'Wrong historical seat election')
    if source['format']!='tree':require(source['heading'] in table.headings,'Wrong historical seat area')
    seat_column=any(a.get('id')=='hseggi' and v=='Seggi' for row in table.rows for a,v in row)
    if not seat_column:
        # A municipality can repeat the college winner: only a college endpoint may yield a seat.
        require(parse_qs(urlsplit(url).query).get('tpe')==['L'],'Seat winner outside a college')
        annotated=[v for row in table.rows for a,v in row if re.fullmatch(r'lista\d+',a.get('id','')) and '(ELETTO)' in a.get('annotation','')]
        if annotated:
            require(record['type']=='S' and record['date']=='09/04/2006' and 1<=len(annotated)<=2,'Unexpected historical elected annotations')
            return [dict(name=name,members=[name],seats=1) for name in annotated],{}
        blocks=[];current=None
        for row in table.rows:
            ids=[a['id'] for a,v in row if re.fullmatch(r'candidato\d+',a.get('id',''))]
            if ids:
                current=dict(id=ids[0],elected=any(normalize(v)=='eletto' for a,v in row),members=[]);blocks.append(current)
            elif current is not None:
                linked=[v for a,v in row if v and ('hlista' in a.get('headers','').split() or (a.get('colspan')=='2' and not a.get('headers')))]
                current['members'].extend(linked)
        winners=[b for b in blocks if b['elected']]
        require(len(winners)==1 and winners[0]['members'],'Missing or ambiguous ministerial elected marker')
        members=winners[0]['members'];name=' · '.join(members)
        return [dict(name=name,members=members,seats=1)],{}
    blocks=[];current=None;seen=set();declared=[];details={}
    for row in table.rows:
        leaders=[(a['id'],v) for a,v in row if re.fullmatch(r'candidato\d+',a.get('id',''))]
        lists=[(a['id'],v) for a,v in row if re.fullmatch(r'lista\d+(?:_\d+)?',a.get('id',''))]
        if leaders:
            key,name=leaders[0];require(key not in seen,'Duplicate historical leader');seen.add(key)
            current=dict(id=key,leader=name,members=[],seats=0);blocks.append(current)
        elif lists:
            key,name=lists[0];require(key not in seen and name,'Duplicate historical list');seen.add(key)
            seats=cell_count(row)
            if source['format']=='linked':
                require(current is not None and any(a.get('id')==key and current['id'] in a.get('headers','').split() for a,v in row),'Historical list attached to wrong leader')
                current['members'].append(name);current['seats']+=seats
            else:blocks.append(dict(name=name,members=[name],seats=seats))
            details[normalize(name)]=dict(listSeats=seats)
        if any(a.get('id','').startswith('htotalecoalizione') for a,v in row):
            require(current is not None and cell_count(row)==current['seats'],'Coalition sum disagrees with official total')
        if any('hseggi' in a.get('headers','').split() and 'htotalecomplessivo' in a.get('headers','') for a,v in row):declared.append(cell_count(row))
    require(len(declared)==1 and blocks and sum(b['seats'] for b in blocks)==declared[0],'Historical seat rows do not reconcile')
    for block in blocks:
        require(block['members'],'Empty historical seat group')
        if source['format']=='linked':
            block['name']=block['members'][0] if len(block['members'])==1 else record.get('coalitionLabels',{}).get(block['leader'],'Coalizione '+block['leader'])
            if len(block['members'])>1:
                gid='seats-'+sha256((source['id']+':'+normalize(block['name'])).encode()).hexdigest()[:16]
                for name in block['members']:details[normalize(name)].update(coalitionID=gid,coalitionName=block['name'])
    return [b for b in blocks if b['seats']>0],details


def allocation(record,fetcher=download_page):
    capacities={'camera':574,'senato':237} if record['date']=='18/04/1948' else {'camera':630,'senato':315}
    require(record['chamber'] in capacities and record['totalSeats']==capacities[record['chamber']],'Wrong historical chamber capacity')
    require(record['parts'] and len({s['id'] for s in record['parts']})==len(record['parts']),'Duplicate historical seat component')
    totals=Counter();names={};details={};audit=[];pages=[]
    for source in record['parts']:
        require(source['format'] in ('flat','linked','tree'),'Unsupported historical seat format')
        frontier=[source['url']];visited=set();component=[];leaf_count=0;leaf_keys=set()
        area=official_page(source['url']).get('tpa')
        while frontier:
            require(len(visited)+len(frontier)<=700 and not visited.intersection(frontier),'Duplicate or excessive seat geography')
            def get(url):
                q=official_page(url)
                require(q['tpel']==[record['type']] and q['dtel']==[record['date']] and q.get('tpa')==area,'Historical seat URL belongs to another election or area')
                return url,fetcher(url)
            with ThreadPoolExecutor(max_workers=3) as pool:responses=list(pool.map(get,frontier))
            next_pages=[]
            for url,raw in responses:
                visited.add(url);audit.append(dict(url=url,sha256=sha256(raw).hexdigest()))
                parsed=read_table(raw,record,source,url)
                if parsed is None:
                    require(source['format']=='tree','Historical results table missing')
                    children=child_pages(raw,url);require(children,'Historical college selector missing');next_pages.extend(children)
                else:
                    q=parse_qs(urlsplit(url).query)
                    identity=tuple((k,tuple(q.get(k,[]))) for k in ('tpa','tpe','ne1','ne2','ne3'))
                    require(identity not in leaf_keys,'Duplicate historical seat constituency');leaf_keys.add(identity)
                    groups,part_details=parsed;component.extend(groups);leaf_count+=1
                    if source.get('listMetadata'):
                        require(not set(details).intersection(part_details),'Duplicate historical list metadata');details.update(part_details)
            require(len(next_pages)==len(set(next_pages)),'Duplicate historical college URL');frontier=next_pages
        require(sum(b['seats'] for b in component)==source['expectedSeats'],'Historical seat component incomplete')
        if source.get('expectedColleges'):require(leaf_count==source['expectedColleges'],'Wrong number of elected colleges')
        for group in component:
            # Keep different ballot components distinct; never assign coalition wins to its largest party.
            identity=source['id']+':'+normalize(group['name']);key='seats-'+sha256(identity.encode()).hexdigest()[:16]
            totals[key]+=group['seats'];names[key]=(group['name'],source['label'])
        pages.append(dict(label=source['label'],url=source['url']))
    require(sum(totals.values())==record['totalSeats'],'Historical chamber incomplete')
    groups=[dict(id=key,name=names[key][0],detail=names[key][1],seats=value) for key,value in totals.items()]
    return dict(chamber=record['chamber'],totalSeats=record['totalSeats'],unassignedSeats=0,groups=groups,
                sourceURL=record['parts'][0]['url'],sourceLabel='Eligendo · Archivio',sourcePages=pages,sourceDocuments=audit,
                coverage=('Intera Camera' if record['chamber']=='camera' else 'Senato elettivo')+' · riparto storico',
                checkedAt=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),listResults=details,
                note='Riparto dei seggi pubblicato da Eligendo, distinto per componenti e perimetri indicati in legenda. Le quote proporzionali e uninominali non sono sovrapposte. I conteggi provengono dalle colonne Seggi o dalle indicazioni ministeriali esplicite di eletto, senza dedurli dai voti. I collegamenti uninominali restano quelli della fonte: non sono attribuiti arbitrariamente ai singoli partiti. Non rappresenta i gruppi parlamentari attuali.'+(' Senatori a vita esclusi.' if record['chamber']=='senato' else '')+record.get('note',''))
