"""Fetch official sources, validate, and publish an atomic set of JSON documents.
Python standard library only. No credentials are needed to read Ministry sources.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from aggregate import build, build_tables, require
from identities import compile_registry, candidate_catalog
from seats import apply_seats
from party_seats import apply_party_seats
from seat_groups import consolidate_seats

ROOT = Path(__file__).resolve().parents[1]
MAX_DOWNLOAD = 160_000_000
MAX_EXTRACTED = 50_000_000
ALLOWED_HOSTS = {'elezionistorico.interno.gov.it', 'elezioni.interno.gov.it', 'dait.interno.gov.it'}

def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def official_url(url):
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == 'https' and parsed.hostname in ALLOWED_HOSTS and parsed.port in (None,443), 'Unapproved source URL')
    prefix = '/documenti/opendata/' if parsed.hostname == 'dait.interno.gov.it' else '/daithome/documenti/opendata/'
    require(parsed.path.startswith(prefix), 'Unapproved source path')
    require(not parsed.username and not parsed.password, 'Unexpected URL credentials')

class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        official_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    temporary.chmod(0o644)
    temporary.replace(path)

def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n').encode()

def fetch(config, cache_dir):
    url = config['downloadURL']
    official_url(url)
    cache_dir.mkdir(parents=True,exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()
    raw_path, metadata_path = cache_dir/(key+'.bin'), cache_dir/(key+'.json')
    metadata = {}
    if raw_path.exists() and metadata_path.exists():
        try: metadata = json.loads(metadata_path.read_text())
        except (ValueError,OSError): pass
    headers = {'User-Agent': 'Electo-OpenData/1.0 (+https://github.com/IlMona98/electo-data)'}
    if metadata.get('etag'): headers['If-None-Match'] = metadata['etag']
    if metadata.get('lastModified'): headers['If-Modified-Since'] = metadata['lastModified']
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.build_opener(OfficialRedirect()).open(request, timeout=90) as response:
            official_url(response.url)
            require(response.status==200, 'Unexpected upstream HTTP status')
            require(int(response.headers.get('Content-Length','0')) <= MAX_DOWNLOAD, 'Source too large')
            raw = response.read(MAX_DOWNLOAD+1)
            require(len(raw) <= MAX_DOWNLOAD, 'Source too large')
            require(not raw.lstrip().lower().startswith((b'<html',b'<!doctype')), 'HTML instead of election data')
            metadata = dict(etag=response.headers.get('ETag'), lastModified=response.headers.get('Last-Modified'), acquiredAt=now(), sha256=hashlib.sha256(raw).hexdigest())
    except urllib.error.HTTPError as error:
        if error.code != 304 or not raw_path.exists() or not metadata.get('sha256'): raise
        raw = raw_path.read_bytes()
        require(hashlib.sha256(raw).hexdigest()==metadata['sha256'], 'Corrupt download cache')
    if config.get('adapter') == 'aggregate-tables':
        names = [config['tables'][key] for key in ['stats','lists','nationalStats','nationalLists']]
        require(len(set(names)) == 4, 'Duplicate aggregate table configuration')
        members = {}
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for name in names:
                info = archive.getinfo(name)
                require(not info.flag_bits & 1 and info.file_size <= MAX_EXTRACTED, 'Invalid or oversized ZIP member')
                members[name] = archive.read(info)
        election = build_tables(members, config)
    else:
        member = config.get('zipMember')
        if member:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                info = archive.getinfo(member)
                require(not info.flag_bits & 1 and info.file_size <= MAX_EXTRACTED, 'Invalid or oversized ZIP member')
                data = archive.read(info)
        else:
            data = raw
        require(len(data) <= MAX_EXTRACTED, 'Extracted source too large')
        election = build(data, config)
    election['retrievedAt'] = metadata['acquiredAt']
    require(all(t['electors'] > 0 and 0 <= t['voters'] <= t['electors'] for t in election['territories']), 'Invalid aggregate turnout')
    checked_at = now()
    election['checkedAt'] = checked_at
    # Cache only after normalization succeeds. Never replace public data on failure.
    atomic_write(raw_path,raw)
    metadata['checkedAt'] = checked_at
    atomic_write(metadata_path,encode(metadata))
    return election

def publish(elections, output):
    require(elections and len({e['id'] for e in elections})==len(elections),'Duplicate or empty elections')
    output.mkdir(parents=True,exist_ok=True)
    archive = dict(schemaVersion=1, retrievedAt=min(e['retrievedAt'] for e in elections), checkedAt=min(e['checkedAt'] for e in elections), elections=elections)
    # Immutable names make catalog -> detail reads coherent across deployments.
    entries=[]
    for election in elections:
        document=dict(schemaVersion=1,retrievedAt=election['retrievedAt'],checkedAt=election['checkedAt'],elections=[election])
        payload=encode(document)
        digest=hashlib.sha256(payload).hexdigest()
        name=f"{election['id']}-{digest[:16]}.json"
        atomic_write(output/name,payload)
        entries.append({k:v for k,v in election.items() if k not in ('territories',) } | dict(national=election['territories'][0], path=name, sha256=digest, territoryCount=len(election['territories'])))
    atomic_write(output/'catalog.json',encode(dict(schemaVersion=1,checkedAt=archive['checkedAt'],elections=entries)))
    atomic_write(output/'archive.json',encode(archive))
    return archive

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cache',type=Path,default=ROOT/'.cache')
    parser.add_argument('--output',type=Path,default=ROOT/'public/v1')
    args=parser.parse_args()
    configs=json.loads((ROOT/'sources.json').read_text())
    registry=compile_registry(json.loads((ROOT/'config/identities.json').read_text()), ROOT/'public')
    elections=[]
    for config in configs:
        print('Checking',config['id'],flush=True)
        elections.append(fetch(config,args.cache))
    # All sources must succeed before the deployable set is updated.
    apply_seats(elections,json.loads((ROOT/'config/seats.json').read_text()))
    apply_party_seats(elections,json.loads((ROOT/'config/party-seats.json').read_text()))
    consolidate_seats(elections,json.loads((ROOT/'config/seat-groups.json').read_text()))
    archive=publish(elections,args.output)
    atomic_write(args.output/'identities.json',encode(registry))
    atomic_write(args.output/'identity-candidates.json',encode(candidate_catalog(elections)))
    print('Validated',len(archive['elections']),'elections; source checked:',archive['checkedAt'])

if __name__=='__main__': main()
