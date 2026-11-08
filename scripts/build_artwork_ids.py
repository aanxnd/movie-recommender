"""Build a deterministic IMDb companion without modifying prepared reference data."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path


def build(source, prepared, destination):
    source, prepared, destination = Path(source), Path(prepared), Path(destination)
    manifest = json.loads((prepared / 'manifest.json').read_text(encoding='utf-8'))
    raw_catalog = (prepared / 'catalog.json').read_bytes()
    catalog_hash = hashlib.sha256(raw_catalog).hexdigest()
    if manifest['artifact_checksums']['catalog.json'] != catalog_hash:
        raise ValueError('Prepared catalogue checksum mismatch')
    movies_bytes = (source / 'movies.csv').read_bytes()
    if hashlib.sha256(movies_bytes).hexdigest() != manifest['source_checksums']['movies.csv']:
        raise ValueError('Source movies do not match prepared reference')
    catalog = {r['movie_id']: r['title'] for r in json.loads(raw_catalog)['movies']}
    with (source / 'movies.csv').open(encoding='utf-8-sig', newline='') as stream:
        movies = {int(r['movieId']): r['title'] for r in csv.DictReader(stream)}
    if movies != catalog:
        raise ValueError('Source catalogue identity mismatch')
    links, seen = [], set()
    with (source / 'links.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            mid, imdb = int(row['movieId']), row.get('imdbId') or ''
            if mid not in catalog or mid in seen:
                raise ValueError('Invalid or duplicate link identity')
            seen.add(mid)
            if imdb.isascii() and imdb.isdigit() and 0 < int(imdb) < 10**10:
                links.append([mid, 'tt' + imdb.zfill(7)])
    if seen != set(catalog):
        raise ValueError('Incomplete source link inventory')
    data = {'schema': 1, 'catalog_sha256': catalog_hash, 'links': sorted(links)}
    packed = gzip.compress(json.dumps(data, separators=(',', ':'), sort_keys=True).encode(), mtime=0)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'movielens-imdb.json.gz').write_bytes(packed)
    pins = {'schema': 1, 'catalog_sha256': catalog_hash,
            'file_sha256': hashlib.sha256(packed).hexdigest(),
            'source_movies_sha256': hashlib.sha256(movies_bytes).hexdigest(),
            'source_links_sha256': hashlib.sha256((source / 'links.csv').read_bytes()).hexdigest(),
            'mapped_movies': len(links)}
    (destination / 'movielens-imdb.sources.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
    (destination / 'MOVIELENS_README.txt').write_bytes((source / 'README.txt').read_bytes())
    return pins


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.prepared, args.output)))
