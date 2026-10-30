"""Attach reviewed institutional seat allocations; never estimate seats from votes."""
from aggregate import require
from identities import normalize
from urllib.parse import urlsplit
import copy


def apply_seats(elections, document):
    require(document.get('schemaVersion')==1 and isinstance(document.get('elections'),list),'Invalid seats document')
    known={e['id']:e for e in elections};seen=set()
    for record in document['elections']:
        key=record['electionID']
        require(key in known and key not in seen,'Unknown or duplicate seat election')
        seen.add(key);election=known[key];value=copy.deepcopy(record['seats'])
        total=value['totalSeats'];vacant=value['unassignedSeats'];groups=value['groups']
        require(value['chamber']==election.get('chamber') and value['chamber'] in ('camera','senato'),'Seats belong to another chamber')
        require(type(total) is int and 1<=total<=1000 and type(vacant) is int and 0<=vacant<=total,'Invalid seat totals')
        require(groups and len(groups)<=total and len({g['id'] for g in groups})==len(groups),'Duplicate or empty seat groups')
        require(all(g['id'] and g['name'] and type(g['seats']) is int and 1<=g['seats']<=total for g in groups),'Invalid seat group')
        require(sum(g['seats'] for g in groups)+vacant==total,'Assigned and vacant seats do not match chamber total')
        url=urlsplit(value['sourceURL'])
        require(url.scheme=='https' and url.hostname=='data.ipu.org' and url.path.startswith('/parliament/IT/'),'Invalid seat source')
        require(all(isinstance(value.get(k),str) and value[k].strip() for k in ('sourceLabel','coverage','note')),'Missing seat attribution')
        names={normalize(r['name']):r['id'] for r in election['territories'][0]['results']}
        for group in groups:
            if normalize(group['name']) in names: group['resultID']=names[normalize(group['name'])]
        election['seats']=value
    return elections
