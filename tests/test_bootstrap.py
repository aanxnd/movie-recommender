from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import tarfile
from threading import Event
from urllib.error import URLError

import pytest

from app import bootstrap as b
from scripts.prepare_movielens import prepare_movielens


@pytest.fixture
def release(tmp_path):
    source = tmp_path/'source'
    source.mkdir()
    (source/'movies.csv').write_text('movieId,title,genres\n1,A (2000),Drama\n2,B (2001),Action\n')
    (source/'ratings.csv').write_text('userId,movieId,rating\n1,1,1\n1,2,5\n')
    (source/'README.txt').write_text('Synthetic terms')
    prepared = prepare_movielens(source,tmp_path/'original')
    archive = tmp_path/'release.tar.gz'
    with tarfile.open(archive,'w:gz') as stream:
        stream.add(prepared,arcname='ml-32m-v1')
    content = archive.read_bytes()
    return prepared, content, hashlib.sha256(content).hexdigest()


def mock_download(monkeypatch, content, declared=None, callback=None):
    class Response(io.BytesIO):
        headers = {'Content-Length': str(len(content) if declared is None else declared)}
    class Opener:
        def open(self,url,timeout):
            assert url == b.RELEASE_URL and timeout == b.IO_TIMEOUT
            if callback: callback()
            return Response(content)
    monkeypatch.setattr(b,'build_opener',lambda *args: Opener())


def test_download_extract_publish_marker_and_reuse(release,tmp_path,monkeypatch):
    original, content, digest = release
    mock_download(monkeypatch,content)
    destination = tmp_path/'runtime/ml-32m-v1'
    assert b.ensure_prepared(destination,b.RELEASE_URL,digest) == destination
    assert {p.name:p.read_bytes() for p in destination.iterdir()} == {p.name:p.read_bytes() for p in original.iterdir()}
    marker=json.loads(b.marker_path(destination).read_text())
    assert marker['expected_archive_sha256'] == digest and marker['verification']=='pinned archive'
    assert not list(destination.parent.glob('.download-*'))
    assert not list(destination.parent.glob('.staging-*'))
    monkeypatch.setattr(b,'download_archive',lambda *args: pytest.fail('Unexpected download'))
    monkeypatch.setattr(b,'checksum',lambda *args: pytest.fail('Unexpected rehash'))
    assert b.ensure_prepared(destination,b.RELEASE_URL,digest) == destination


def test_existing_local_artifacts_do_not_download(release,monkeypatch):
    monkeypatch.setattr(b,'download_archive',lambda *args: pytest.fail('Unexpected download'))
    assert b.ensure_prepared(release[0]) == release[0]


@pytest.mark.parametrize('case', ['hash','truncated','size'])
def test_failed_download_never_publishes(release,tmp_path,monkeypatch,case):
    _, content, digest = release
    mock_download(monkeypatch,content,declared=len(content)+1 if case=='truncated' else None)
    if case=='size': monkeypatch.setattr(b,'MAX_DOWNLOAD_BYTES',1)
    if case=='hash': digest='0'*64
    destination=tmp_path/'runtime/ml-32m-v1'
    with pytest.raises(b.BootstrapError): b.ensure_prepared(destination,b.RELEASE_URL,digest)
    assert not destination.exists() and not b.marker_path(destination).exists()
    assert not list(destination.parent.glob('.download-*'))


@pytest.mark.parametrize('url', ['http://github.com/aanxnd/movie-recommender/releases/download/data-v1/ml-32m-v1.tar.gz','https://evil.example/archive','https://user:secret@github.com/aanxnd/movie-recommender/releases/download/data-v1/ml-32m-v1.tar.gz'])
def test_untrusted_configuration_is_rejected_without_download(tmp_path,url,monkeypatch):
    monkeypatch.setattr(b,'download_archive',lambda *args: pytest.fail('Unexpected download'))
    with pytest.raises(b.BootstrapError) as error: b.ensure_prepared(tmp_path/'missing',url,'0'*64)
    assert url not in str(error.value)


def test_missing_data_is_opt_in(tmp_path):
    with pytest.raises(b.BootstrapError,match='configure'): b.ensure_prepared(tmp_path/'missing')


@pytest.mark.parametrize('name,kind', [
    ('/absolute',tarfile.REGTYPE),('../escape',tarfile.REGTYPE),
    ('ml-32m-v1/../escape',tarfile.REGTYPE),('other/file',tarfile.REGTYPE),
    ('ml-32m-v1/README.txt',tarfile.SYMTYPE),('ml-32m-v1/README.txt',tarfile.LNKTYPE),
    ('ml-32m-v1/README.txt',tarfile.CHRTYPE),('ml-32m-v1/nested',tarfile.DIRTYPE),
])
def test_unsafe_archive_members_are_rejected_before_extraction(tmp_path,name,kind):
    archive=tmp_path/'bad.tar.gz'
    with tarfile.open(archive,'w:gz') as stream:
        member=tarfile.TarInfo(name);member.type=kind;member.linkname='/outside'
        stream.addfile(member,io.BytesIO())
    staging=tmp_path/'staging';staging.mkdir()
    with pytest.raises(b.BootstrapError): b.extract_archive(archive,staging)
    assert not list(staging.iterdir())


@pytest.mark.parametrize('case',['duplicate','missing','expanded','members'])
def test_archive_inventory_and_bounds(tmp_path,monkeypatch,case):
    archive=tmp_path/'bad.tar.gz'
    if case=='expanded': monkeypatch.setattr(b,'MAX_EXTRACTED_BYTES',0)
    with tarfile.open(archive,'w:gz') as stream:
        names=['ml-32m-v1/README.txt']*(17 if case=='members' else 2 if case=='duplicate' else 1)
        for name in names:
            member=tarfile.TarInfo(name);member.size=1
            stream.addfile(member,io.BytesIO(b'x'))
    with pytest.raises(b.BootstrapError): b.extract_archive(archive,tmp_path/'staging')


def test_invalid_prepared_contents_never_publish(release,tmp_path,monkeypatch):
    original, _, _=release
    (original/'manifest.json').write_text('{}')
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w:gz') as stream: stream.add(original,arcname='ml-32m-v1')
    content=buffer.getvalue();mock_download(monkeypatch,content)
    destination=tmp_path/'runtime/ml-32m-v1'
    with pytest.raises(b.BootstrapError): b.ensure_prepared(destination,b.RELEASE_URL,hashlib.sha256(content).hexdigest())
    assert not destination.exists()


def test_concurrent_startups_download_and_publish_once(release,tmp_path,monkeypatch):
    _,content,digest=release
    entered=Event();release_download=Event();calls=[]
    def callback():
        calls.append(True);entered.set();assert release_download.wait(5)
    mock_download(monkeypatch,content,callback=callback)
    destination=tmp_path/'runtime/ml-32m-v1'
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(b.ensure_prepared,destination,b.RELEASE_URL,digest)
        assert entered.wait(5)
        second=pool.submit(b.ensure_prepared,destination,b.RELEASE_URL,digest)
        assert not destination.exists()
        release_download.set()
        assert first.result(timeout=10)==second.result(timeout=10)==destination
    assert len(calls)==1


def test_transport_retries_are_bounded_and_sanitized(tmp_path,monkeypatch):
    calls=[]
    class Opener:
        def open(self,*args,**kwargs):
            calls.append(True);raise URLError('private transport details')
    monkeypatch.setattr(b,'build_opener',lambda *args:Opener())
    monkeypatch.setattr(b.time,'sleep',lambda *args:None)
    with pytest.raises(b.BootstrapError,match='bounded retries') as error:
        b.download_archive(b.RELEASE_URL,'0'*64,tmp_path)
    assert len(calls)==3 and 'private' not in str(error.value)
    assert not list(tmp_path.iterdir())


def test_interrupted_response_cleans_partial_files(tmp_path, monkeypatch):
    from http.client import IncompleteRead
    class Response:
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): raise IncompleteRead(b'partial', 100)
    class Opener:
        def open(self, *args, **kwargs): return Response()
    monkeypatch.setattr(b, 'build_opener', lambda *args: Opener())
    monkeypatch.setattr(b.time, 'sleep', lambda *args: None)
    with pytest.raises(b.BootstrapError, match='bounded retries'):
        b.download_archive(b.RELEASE_URL, '0'*64, tmp_path)
    assert not list(tmp_path.iterdir())
