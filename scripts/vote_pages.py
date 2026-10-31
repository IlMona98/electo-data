"""Read dated ministerial national and territorial result/turnout tables."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from aggregate import require, slug
from identities import normalize
from seats import SeatTable, download_page, official_page
from historical_seats import child_pages

class TurnoutTable(SeatTable):
    def handle_starttag(self,tag,attrs):
        if tag=='table':
            attrs=dict(attrs)
            attrs['summary']='Risultato elezione' if attrs.get('summary')=='Riepilogo elezione' else 'Other'
            attrs=list(attrs.items())
        super().handle_starttag(tag,attrs)

def integer(value):
    require(re.fullmatch(r'\d+(?:\.\d{3})*',value) is not None,'Invalid ministerial voting count')
    return int(value.replace('.',''))

def parse_votes(raw, config, url):
    query=official_page(url)
    require(query['tpel']==[config['type']] and query['dtel']==[config['date']], 'Wrong vote source date or chamber')
    require(len(raw)<=2_000_000,'Voting page too large')
    text=raw.decode('utf-8-sig');table=SeatTable();table.feed(text)
    heading=config['headingPrefix']+' Area ITALIA'
    valid=[h for h in table.headings if h==heading or h.startswith(heading+' '+config['level']+' ')]
    require(table.tables==1 and len(valid)==1,'Wrong election or voting area')
    require(not query.get('ne2') and not query.get('ne3'),'Voting page is below the configured territorial level')
    is_national=query.get('tpe')==['A'] and not query.get('ne1')
    require(is_national or (query.get('ne1') and query.get('tpe')==(['I']if config['type']=='C'else['R'])),'Wrong territorial voting route')
    require((valid[0]==heading)==is_national,'Voting territory does not match heading')
    stats=TurnoutTable();stats.feed(text)
    def stat(key):
        values=[v for row in stats.rows for a,v in row if a.get('headers')==key and a.get('abbr')!='percentuale']
        require(len(values)==1,'Missing or duplicate turnout value: '+key)
        return integer(values[0])
    electors,voters=stat('helettori'),stat('hvotanti')
    require(0<voters<=electors,'Invalid territorial turnout')
    rows=[];declared=[];seen=set()
    for row in table.rows:
        names=[v for a,v in row if re.fullmatch(r'lista\d+',a.get('id',''))]
        if names:
            values=[v for a,v in row if 'hvoti'in a.get('headers','').split() and a.get('abbr')!='percentuale']
            require(len(names)==len(values)==1 and normalize(names[0])not in seen,'Duplicate list or missing votes')
            seen.add(normalize(names[0]));rows.append(dict(id=slug(names[0]),name=names[0],votes=integer(values[0])))
        for a,v in row:
            if 'htotalecomplessivovoti'in a.get('headers','').split() and 'hvoti'in a.get('headers','').split():declared.append(integer(v))
    require(rows and len(declared)==1 and sum(r['votes']for r in rows)==declared[0]<=voters,'Voting rows disagree with published total')
    name='Italia' if is_national else valid[0].removeprefix(heading+' '+config['level']+' ')
    return dict(id='italia'if is_national else slug(name),name=name,level='Nazionale'if is_national else config['level'],electors=electors,voters=voters,results=rows)

def build(config, fetcher=download_page):
    url=config['downloadURL'];raw=fetcher(url);national=parse_votes(raw,config,url)
    urls=child_pages(raw,url)
    require(len(urls)==config['expectedTerritories'] and len(set(urls))==len(urls),'Incomplete historical voting territories')
    with ThreadPoolExecutor(max_workers=4)as pool:documents=list(zip(urls,pool.map(fetcher,urls)))
    territories=[parse_votes(body,config,u)for u,body in documents]
    require(len({t['id']for t in territories})==len(territories),'Duplicate historical voting area')
    by_name={normalize(r['name']):r['name']for r in national['results']}
    aliases={normalize(k):normalize(v)for k,v in config.get('listAliases',{}).items()}
    for territory in territories:
        for row in territory['results']:
            key=aliases.get(normalize(row['name']),normalize(row['name']))
            require(key in by_name,'Unreviewed territorial voting label: '+row['name'])
            target=slug(by_name[key])
            if target!=row['id']:row['nationalResultID']=target
    for key in ['electors','voters']:
        require(sum(t[key]for t in territories)==national[key],'Historical turnout does not reconcile: '+key)
    totals=Counter()
    for t in territories:
        for r in t['results']:totals[r.get('nationalResultID',r['id'])]+=r['votes']
    require(totals==Counter({r['id']:r['votes']for r in national['results']}),'Historical territorial votes do not reconcile')
    private={'adapter','downloadURL','type','date','headingPrefix','level','expectedTerritories','listAliases'}
    result={k:v for k,v in config.items()if k not in private}
    stamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    result.update(territories=[national]+sorted(territories,key=lambda t:t['name']),sourceSHA256=sha256(raw).hexdigest(),sourceUnits=len(territories),retrievedAt=stamp,checkedAt=stamp,
                  sourceDocuments=[dict(url=u,sha256=sha256(body).hexdigest())for u,body in [(url,raw)]+documents])
    return result
