from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.artwork_images import ImageCache, ImageUnavailable, MAX_BYTES, RETENTION, TTL, download_image, trakt_image_url
from app.main import create_app
from test_api import api_paths
from test_artwork import store, metadata, images

URL = 'https://media.trakt.tv/movies/481/medium/poster.webp'
# Small synthetic RIFF payload exercises the transport/cache framing, not a film asset.
WEBP = b'RIFF' + (16).to_bytes(4, 'little') + b'WEBPVP8 ' + b'\x04\0\0\0test'


@pytest.mark.parametrize('value', [
    URL, URL.removeprefix('https://'),
    'https://walter-r2.trakt.tv/images/movies/000/000/481/posters/thumb/hash.jpg.webp',
    'walter-r2.trakt.tv/images/movies/000/000/481/posters/full/hash.png.webp',
])
def test_only_documented_or_live_verified_identity_bound_image_paths(value):
    assert trakt_image_url(value, 'movies', 481, 'poster').startswith('https://')
    assert trakt_image_url(value, 'shows', 481, 'poster') is None
    assert trakt_image_url(value, 'movies', 482, 'poster') is None
    assert trakt_image_url(value, 'movies', 481, 'fanart') is None


@pytest.mark.parametrize('value', [None, [], {}, 'http://media.trakt.tv/movies/481/medium/poster.webp',
    URL + '?key=secret', URL + '#fragment', URL.replace('media.trakt.tv', 'media.trakt.tv.evil.invalid'),
    URL.replace('media.trakt.tv', 'localhost'), URL.replace('media.trakt.tv', '127.0.0.1'),
    URL.replace('media.trakt.tv', 'user:password@media.trakt.tv'), URL.replace('media.trakt.tv', 'media.trakt.tv:443'),
    URL.replace('/medium/', '/../medium/'), URL.replace('/medium/', '/%2e%2e/medium/'), URL.replace('.webp', '.svg'),
    URL.replace('/481/', '/0/'), URL.replace('poster', 'logo'), URL.replace('media.trakt.tv', 'MEDIA.TRAKT.TV'),
])
def test_rejects_untrusted_urls_without_network(value):
    assert trakt_image_url(value) is None
    assert ImageCache(fetch=lambda *a, **k: pytest.fail('network')).get(value) is None


def response(status=200, data=WEBP, **headers):
    stream = io.BytesIO(data)
    return SimpleNamespace(status=status, read=stream.read,
        getheader=lambda name, default=None: {'Content-Type': 'image/webp', **headers}.get(name, default))


def download(reply, *, ip='8.8.8.8', monotonic=lambda: 0):
    calls = []
    class Connection:
        def __init__(self, host, address, timeout): calls.append((host, address, timeout))
        def request(self, method, path, headers): calls.append((method, path, headers))
        def getresponse(self): return reply
        def close(self): calls.append('closed')
    data = download_image(URL, deadline=6, monotonic=monotonic,
        resolver=lambda *a, **kw: [(None, None, None, None, (ip, 443))], connection_factory=Connection)
    return data, calls


def test_download_pins_public_address_uses_original_tls_host_and_sends_no_credentials():
    data, calls = download(response(**{'Content-Length': str(len(WEBP))}))
    assert data == WEBP and calls[0] == ('media.trakt.tv', '8.8.8.8', 2.5)
    assert calls[1][0:2] == ('GET', '/movies/481/medium/poster.webp')
    assert set(calls[1][2]) == {'Accept', 'User-Agent'} and calls[-1] == 'closed'


@pytest.mark.parametrize('ip', ['127.0.0.1', '10.0.0.1', '169.254.169.254', '::1', 'fc00::1', '192.0.2.1'])
def test_private_reserved_destinations_are_rejected(ip):
    with pytest.raises(ImageUnavailable): download(response(), ip=ip)


@pytest.mark.parametrize('reply', [response(302), response(404), response(429, **{'Retry-After': '60'}),
    response(**{'Content-Type': 'text/html'}), response(**{'Content-Length': str(MAX_BYTES + 1)}),
    response(**{'Content-Length': 'invalid'}), response(**{'Content-Length': '21'}),
    response(data=b'not webp'), response(data=WEBP[:-1]), response(data=WEBP + b'x' * MAX_BYTES)])
def test_redirects_rate_limits_wrong_mime_sizes_and_corrupt_framing_are_not_served(reply):
    with pytest.raises(ImageUnavailable): download(reply)


def test_deadline_stops_work():
    with pytest.raises(ImageUnavailable): download(response(), monotonic=lambda: 7)


def test_memory_disk_etag_stale_ceiling_and_transient_negative_cache(tmp_path):
    now = [100.0]; calls = []
    def fetch(*args, **kwargs): calls.append(1); return WEBP
    cache = ImageCache(tmp_path, fetch=fetch, clock=lambda: now[0])
    image = cache.get(URL)
    assert image.data == WEBP and cache.get(URL) is image and len(calls) == 1
    assert image.etag == '"' + hashlib.sha256(WEBP).hexdigest() + '"'
    disk = ImageCache(tmp_path, fetch=lambda *a, **k: pytest.fail('disk miss'))
    assert disk.get(URL).data == WEBP
    now[0] += TTL + 1
    def unavailable(*a, **k): calls.append(1); raise ImageUnavailable(429, 120)
    cache.fetch = unavailable
    assert cache.get(URL).data == WEBP
    assert cache.get(URL).data == WEBP and len(calls) == 2
    now[0] += RETENTION
    assert cache.get(URL) is None


def test_invalid_disk_and_download_never_become_cache_hits(tmp_path):
    (tmp_path / (hashlib.sha256(URL.encode()).hexdigest() + '.webp')).write_bytes(b'<html>')
    cache = ImageCache(tmp_path, fetch=lambda *a, **kw: b'not webp')
    assert cache.get(URL) is None
    assert not cache.memory


def test_singleflight_and_only_two_outbound_image_requests(tmp_path):
    started = Event(); release = Event(); calls = []
    def slow(*a, **kw): calls.append(1); started.set(); release.wait(2); return WEBP
    cache = ImageCache(tmp_path, fetch=slow)
    with ThreadPoolExecutor(max_workers=8) as pool:
        first = pool.submit(cache.get, URL)
        assert started.wait(1)
        duplicates = [pool.submit(cache.get, URL) for _ in range(6)]
        second = pool.submit(cache.get, URL.replace('/481/', '/482/'))
        # Additional unique work queues within its deadline, never a third download.
        for _ in range(100):
            if len(calls) == 2: break
            Event().wait(.005)
        third = pool.submit(cache.get, URL.replace('/481/', '/483/'))
        assert len(calls) == 2
        release.set()
        assert first.result().data == WEBP and second.result().data == WEBP
        assert all(f.result().data == WEBP for f in duplicates)
        assert third.result().data == WEBP and len(calls) == 3


def test_image_route_canonical_roles_cache_headers_and_conditionals(api_paths, tmp_path):
    artwork = store(tmp_path, [])
    artwork.fetch = lambda provider, *a, **kw: metadata(images={'poster': [URL]}) if provider == 'trakt' else images()
    artwork.image_cache = ImageCache(tmp_path / 'bytes', fetch=lambda *a, **k: WEBP)
    with TestClient(create_app(*api_paths)) as client:
        client.app.state.artwork = artwork
        result = client.get('/movies/artwork-image/1/poster')
        assert result.status_code == 200 and result.content == WEBP
        assert result.headers['content-type'] == 'image/webp'
        assert result.headers['cache-control'] == 'public, max-age=86400'
        assert result.headers['x-content-type-options'] == 'nosniff'
        assert client.get('/movies/artwork-image/1/poster', headers={'If-None-Match': result.headers['etag']}).status_code == 304
        assert client.get('/movies/artwork-image/999/poster').status_code == 404
        assert client.get('/movies/artwork-image/1/backdrop').status_code == 404
        assert client.get('/movies/artwork-image/1/anything').status_code == 422
        assert client.get('/movies/artwork-image/0/poster').status_code == 422
        for _ in range(56): client.get('/movies/artwork-image/1/poster')
        assert client.get('/movies/artwork-image/1/poster').status_code == 429
