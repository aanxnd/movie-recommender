import gzip
import hashlib
import json
from pathlib import Path

import pytest

from app.artwork_ids import bundled_ids
from scripts.build_artwork_ids import build


def fixture(tmp_path):
    source, prepared, output = [tmp_path / name for name in ('source', 'prepared', 'output')]
    source.mkdir(); prepared.mkdir()
    (source / 'movies.csv').write_text('movieId,title,genres\n1,Test (1999),Drama\n', encoding='utf-8')
    (source / 'links.csv').write_text('movieId,imdbId\n1,1234567\n', encoding='utf-8')
    (source / 'README.txt').write_bytes(b'Original legal terms.\r\n')
    raw = json.dumps({'movies': [{'movie_id': 1, 'title': 'Test (1999)'}]}).encode()
    (prepared / 'catalog.json').write_bytes(raw)
    checksum = hashlib.sha256(raw).hexdigest()
    (prepared / 'manifest.json').write_text(json.dumps({'artifact_checksums': {'catalog.json': checksum},
        'source_checksums': {'movies.csv': hashlib.sha256((source / 'movies.csv').read_bytes()).hexdigest()}}), encoding='utf-8')
    return source, prepared, output, checksum


def test_reproducible_companion_retains_license_and_never_changes_prepared_files(tmp_path):
    source, prepared, output, checksum = fixture(tmp_path)
    before = {p.name: p.read_bytes() for p in prepared.iterdir()}
    pins = build(source, prepared, output)
    packed = (output / 'movielens-imdb.json.gz').read_bytes()
    assert build(source, prepared, output) == pins
    assert (output / 'movielens-imdb.json.gz').read_bytes() == packed
    assert (output / 'MOVIELENS_README.txt').read_bytes() == (source / 'README.txt').read_bytes()
    assert bundled_ids({1: object()}, checksum, output) == {1: 'tt1234567'}
    assert bundled_ids({1: object()}, 'another catalogue', output) == {}
    assert bundled_ids({2: object()}, checksum, output) == {}
    assert {p.name: p.read_bytes() for p in prepared.iterdir()} == before
    (output / 'movielens-imdb.json.gz').write_bytes(packed + b'tamper')
    assert bundled_ids({1: object()}, checksum, output) == {}


@pytest.mark.parametrize('change', ['catalogue', 'source', 'duplicates', 'incomplete'])
def test_builder_rejects_unverified_source_or_inventory(tmp_path, change):
    source, prepared, output, _ = fixture(tmp_path)
    if change == 'catalogue': (prepared / 'catalog.json').write_bytes(b'{}')
    if change == 'source': (source / 'movies.csv').write_bytes(b'wrong source')
    if change == 'duplicates': (source / 'links.csv').write_text('movieId,imdbId\n1,1234567\n1,1234567\n', encoding='utf-8')
    if change == 'incomplete': (source / 'links.csv').write_text('movieId,imdbId\n', encoding='utf-8')
    with pytest.raises(ValueError): build(source, prepared, output)


@pytest.mark.parametrize('data', [[], None, {}, {'schema': 1, 'links': [[1, '../../secret']]}])
def test_malformed_companion_is_safely_ignored(tmp_path, data):
    source, prepared, output, checksum = fixture(tmp_path)
    build(source, prepared, output)
    raw = gzip.compress(json.dumps(data).encode(), mtime=0)
    (output / 'movielens-imdb.json.gz').write_bytes(raw)
    path = output / 'movielens-imdb.sources.json'
    pins = json.loads(path.read_text()); pins['file_sha256'] = hashlib.sha256(raw).hexdigest()
    path.write_text(json.dumps(pins), encoding='utf-8')
    assert bundled_ids({1: object()}, checksum, output) == {}


def test_shipped_companion_checksum_and_size_are_valid():
    root = Path('app/resources')
    pins = json.loads((root / 'movielens-imdb.sources.json').read_text())
    packed = (root / 'movielens-imdb.json.gz').read_bytes()
    assert hashlib.sha256(packed).hexdigest() == pins['file_sha256']
    rows = json.loads(gzip.decompress(packed))['links']
    assert len(rows) == pins['mapped_movies'] == 87585
    assert dict(rows)[170705] == 'tt0185906'
