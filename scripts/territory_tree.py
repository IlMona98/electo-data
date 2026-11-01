"""Disjoint electoral geography from the original municipal ballot units."""
import collections
import csv
import io
import re
from aggregate import decode, require, slug

REGIONS = ['ABRUZZO','BASILICATA','CALABRIA','CAMPANIA','EMILIA ROMAGNA','FRIULI VENEZIA GIULIA','LAZIO','LIGURIA','LOMBARDIA','MARCHE','MOLISE','PIEMONTE','PUGLIA','SARDEGNA','SICILIA','TOSCANA','TRENTINO ALTO ADIGE','UMBRIA',"VALLE D'AOSTA",'VENETO']
def region_name(scope):
    key=re.sub(r'[^A-Z0-9]+',' ',scope.upper()).strip()
    key={'ABRUZZI':'ABRUZZO','EMILIA':'EMILIA ROMAGNA','FRIULI V G':'FRIULI VENEZIA GIULIA'}.get(key,key)
    for region in REGIONS:
        normal=re.sub(r'[^A-Z0-9]+',' ',region).strip()
        if key==normal or re.fullmatch(re.escape(normal)+r' \d+',key):return region
    # A historical constituency must not be presented as a modern region.
    return scope

def build_tree(raw, config, verified):
    reader=csv.DictReader(io.StringIO(decode(raw)),delimiter=';')
    fields=reader.fieldnames or []
    group,place,party,votes,electors,voters=config['columns']
    require(all(k in fields for k in config['columns']+config['unit']),'Incomplete geographic CSV columns')
    college=next((k for k in ['COLLUNINOM','COLLEGIO']if k in fields),None)
    province=next((k for k in ['DESCPROVINCIA','PROVINCIA','DESCRPROV']if k in fields),None)
    units={};seen=set();nodes={};parties={}
    for row in reader:
        unit=tuple(row[k].strip()for k in config['unit']); name=row[party].strip()
        require((unit,name)not in seen,'Duplicate geographic ballot row');seen.add((unit,name))
        scope=row[group].strip();region=region_name(scope)
        levels=[('Regione' if region in REGIONS else config['level'],region)]
        if college and row[college].strip():levels.append(('Collegio',row[college].strip()))
        if province and row[province].strip():levels.append(('Provincia',row[province].strip()))
        levels.append(('Comune',row[place].strip()))
        path=[];parent='italia'
        for level,label in levels:
            require(label,'Missing geographic name')
            tid=slug(parent+'\0'+level+'\0'+label)
            nodes.setdefault(tid,dict(id=tid,parentID=parent,name=label,level=level,electors=0,voters=0,counts=collections.Counter()))
            path.append(tid);parent=tid
        totals=(int(row[electors]),int(row[voters]))
        if unit in units:require(units[unit]==(totals,path),'Ballot belongs to conflicting geographic paths')
        else:
            units[unit]=(totals,path)
            for tid in path:
                nodes[tid]['electors']+=totals[0];nodes[tid]['voters']+=totals[1]
        pid=slug(name);parties[pid]=dict(id=pid,name=name)
        for tid in path:nodes[tid]['counts'][pid]+=int(row[votes])
    national=verified['territories'][0]
    roots=[n for n in nodes.values()if n['parentID']=='italia']
    require(roots and sum(n['electors']for n in roots)==national['electors'] and sum(n['voters']for n in roots)==national['voters'],'Geographic turnout does not match verified national totals')
    combined=collections.Counter()
    for n in roots:combined.update(n['counts'])
    require(dict(combined)=={r['id']:r['votes']for r in national['results']},'Geographic votes do not match verified national totals')
    children=collections.defaultdict(list)
    for n in nodes.values():children[n['parentID']].append(n)
    for node in nodes.values():
        if not (node['electors']>0 and 0<=node['voters']<=node['electors'] and all(v>=0 for v in node['counts'].values()) and sum(node['counts'].values())<=node['voters']):
            # Keep exact source values in the partition, but never display an invalid
            # local turnout/percentage. Empty historical municipalities occur often.
            node['unavailableReason']='Conteggi locali non coerenti o senza elettori nella fonte ministeriale.'
        if children[node['id']]:
            sub=children[node['id']];counts=collections.Counter()
            for child in sub:counts.update(child['counts'])
            require(dict(counts)==dict(node['counts']) and all(sum(c[f]for c in sub)==node[f]for f in ['electors','voters']),'Child territories do not reconcile')
    party_list=sorted(parties.values(),key=lambda p:p['id'])
    party_ids=[p['id']for p in party_list]
    output=[]
    for n in nodes.values():
        counts=n.pop('counts');n['votes']=[counts.get(pid,0)for pid in party_ids]
        n['included']=[i for i,pid in enumerate(party_ids)if pid in counts]
        if any(nodes[p]['level']=='Collegio'for p in ancestor_ids(n,nodes)) and n['level']in ['Provincia','Comune']:
            n['scopeNote']='Dati della parte di territorio inclusa nel collegio selezionato.'
        output.append(n)
    return dict(parties=party_list,nodes=output,levels=list(dict.fromkeys(n['level']for n in output)))

def ancestor_ids(node,nodes):
    path=[];parent=node['parentID']
    while parent!='italia':
        require(parent in nodes and parent not in path,'Invalid geographic parent');path.append(parent);parent=nodes[parent]['parentID']
    return path
