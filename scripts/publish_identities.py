"""Publish owner identities over the last verified archive, without fetching votes."""
import argparse
import json
from pathlib import Path
from aggregate import require
from identities import compile_registry, apply_identity_links, candidate_catalog
from sync import publish, atomic_write, encode

ROOT = Path(__file__).resolve().parents[1]

def publish_registry(source, public):
    public = Path(public)
    output = public / 'v1'
    registry = compile_registry(source, public)
    path = output / 'archive.json'
    if path.exists():
        archive = json.loads(path.read_text())
        require(archive.get('schemaVersion') == 1 and isinstance(archive.get('elections'),list) and archive['elections'], 'No valid verified archive to relink')
        # Canonical links can change; electoral figures and their source timestamps cannot.
        elections = apply_identity_links(archive['elections'],registry)
        publish(elections, output)
        atomic_write(output / 'identity-candidates.json', encode(candidate_catalog(elections)))
    atomic_write(output / 'identities.json', encode(registry))
    return registry

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--public',type=Path,default=ROOT/'public')
    parser.add_argument('--config',type=Path,default=ROOT/'config/identities.json')
    args = parser.parse_args()
    registry = publish_registry(json.loads(args.config.read_text()),args.public)
    print('Published',len(registry['entities']),'identities over existing verified results; no electoral downloads.')

if __name__ == '__main__':main()
