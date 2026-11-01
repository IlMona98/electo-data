"""Publish compact regional detail files without fetching parliamentary seat sources."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile
from aggregate import require
from sync import fetch,encode,atomic_write
from territory_tree import build_tree,ancestor_ids
from publish_territory_search import publish_search
from election_config import load_bundle
ROOT=Path(__file__).resolve().parents[1]

def publish_tree(tree,election,output):
    directory=Path(output)/'territories'/election['id'];nodes={n['id']:n for n in tree['nodes']}
    references=[]
    for root in sorted((n for n in nodes.values()if n['parentID']=='italia'),key=lambda n:n['name']):
        members=[n for n in nodes.values()if n['id']==root['id']or root['id']in ancestor_ids(n,nodes)]
        payload=encode(dict(schemaVersion=1,electionID=election['id'],sourceSHA256=election['sourceSHA256'],parties=tree['parties'],nodes=members))
        digest=hashlib.sha256(payload).hexdigest();name=root['id']+'-'+digest[:16]+'.json'
        atomic_write(directory/name,payload)
        references.append({k:root[k]for k in ['id','name','level','parentID']}|dict(path=name,sha256=digest))
    index=dict(schemaVersion=1,electionID=election['id'],sourceSHA256=election['sourceSHA256'],regions=references,levels=tree['levels'])
    index['search']=publish_search(directory,index)
    atomic_write(directory/'index.json',encode(index));return index

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cache',type=Path,default=ROOT/'.cache');parser.add_argument('--output',type=Path,default=ROOT/'public/v1');args=parser.parse_args()
    archive=json.loads((args.output/'archive.json').read_text());existing={e['id']:e for e in archive['elections']}
    failures=[];success=0
    for config in load_bundle(ROOT)['sources']:
        if config.get('adapter')or config['id']not in existing:continue
        try:
            verified=existing[config['id']];fresh=fetch(config,args.cache)
            require(fresh['sourceSHA256']==verified['sourceSHA256'],'Municipal source differs from published archive; refresh electoral archive first')
            key=hashlib.sha256(config['downloadURL'].encode()).hexdigest();raw=(args.cache/(key+'.bin')).read_bytes()
            if config.get('zipMember'):
                with zipfile.ZipFile(io.BytesIO(raw))as z:raw=z.read(config['zipMember'])
            tree=build_tree(raw,config,verified);publish_tree(tree,verified,args.output);success+=1
            print('Published',config['id'],len(tree['nodes']),'verified geographic nodes',flush=True)
        except Exception as error:
            failures.append(config['id']);print('::warning::'+config['id']+': '+str(error),flush=True)
    require(success>0,'No verified municipal hierarchy could be published')
    print('Published',success,'elections. Preserved previous data for:',', '.join(failures)or'none')
if __name__=='__main__':main()
