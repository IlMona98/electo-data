"""Publish a lightweight global search index from verified territorial documents."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from aggregate import require
from sync import atomic_write,encode
from territory_tree import ancestor_ids
ROOT=Path(__file__).resolve().parents[1]

def publish_search(directory,index):
    directory=Path(directory);entries=[];seen=set()
    for reference in index['regions']:
        require(re.fullmatch(r'[a-f0-9]{16}-[a-f0-9]{16}\.json',reference['path']),'Invalid regional search source')
        raw=(directory/reference['path']).read_bytes()
        require(sha256(raw).hexdigest()==reference['sha256'],'Search source hash mismatch')
        branch=json.loads(raw)
        require(branch['schemaVersion']==1 and branch['electionID']==index['electionID'] and branch['sourceSHA256']==index['sourceSHA256'],'Search source belongs to another election')
        nodes={n['id']:n for n in branch['nodes']}
        require(len(nodes)==len(branch['nodes']) and reference['id']in nodes,'Invalid search source nodes')
        for node in branch['nodes']:
            require(node['id']not in seen,'Duplicate global search territory');seen.add(node['id'])
            ancestors=ancestor_ids(node,nodes)
            require(node['id']==reference['id']or reference['id']in ancestors,'Search node outside its region')
            entry={k:node[k]for k in ['id','name','level']}
            entry.update(regionID=reference['id'],breadcrumb=[nodes[k]['name']for k in reversed(ancestors)])
            if node.get('unavailableReason'):entry['unavailableReason']=node['unavailableReason']
            entries.append(entry)
    require(entries and len(entries)<=30000,'Invalid global search size')
    entries.sort(key=lambda n:(n['name'],n['level'],n['id']))
    payload=encode(dict(schemaVersion=1,electionID=index['electionID'],sourceSHA256=index['sourceSHA256'],entries=entries))
    digest=sha256(payload).hexdigest();name='search-'+digest[:16]+'.json'
    atomic_write(directory/name,payload)
    return dict(path=name,sha256=digest)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'public/v1');args=parser.parse_args()
    elections=json.loads((args.output/'archive.json').read_text())['elections'];count=0
    for election in elections:
        directory=args.output/'territories'/election['id'];path=directory/'index.json'
        if not path.exists():continue
        index=json.loads(path.read_text())
        require(index['sourceSHA256']==election['sourceSHA256'],'Geography needs refreshing before search: '+election['id'])
        index['search']=publish_search(directory,index);atomic_write(path,encode(index));count+=1
        print('Published global search:',election['id'],flush=True)
    require(count>0,'No verified territorial documents available for search')
    print('Published',count,'global search indices; no electoral downloads.')
if __name__=='__main__':main()
