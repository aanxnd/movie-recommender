"""On-demand Trakt image cache; no hotlinking, arbitrary URLs, redirects, or credentials."""
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import http.client
import ipaddress
from pathlib import Path
import re
import socket
import ssl
from threading import BoundedSemaphore, Event, Lock
import tempfile
import time
from urllib.parse import urlsplit

MAX_BYTES = 2 * 1024**2
TTL = 7 * 86400
RETENTION = 30 * 86400
HOSTS = {'media.trakt.tv', 'walter-r2.trakt.tv'}


def trakt_image_url(value, media=None, trakt_id=None, kind=None):
    if not isinstance(value, str) or len(value) > 500:
        return None
    value = value if value.startswith('https://') else 'https://' + value
    try:
        p = urlsplit(value)
        if p.scheme != 'https' or p.netloc not in HOSTS or p.query or p.fragment:
            return None
        if p.netloc == 'media.trakt.tv':
            match = re.fullmatch(r'/(movies|shows)/([1-9][0-9]*)/(?:thumb|medium|full)/(poster|fanart)\.webp', p.path)
            if not match:
                return None
            actual_media, actual_id, actual_kind = match[1], int(match[2]), match[3]
        else:
            match = re.fullmatch(r'/images/(movies|shows)/(\d{3})/(\d{3})/(\d{3})/(posters|fanarts)/(?:thumb|medium|full)/[A-Za-z0-9_-]+\.(?:(?:jpg|png)\.)?webp', p.path)
            if not match:
                return None
            actual_media, actual_id = match[1], int(''.join(match.group(i) for i in (2, 3, 4)))
            actual_kind = 'poster' if match[5] == 'posters' else 'fanart'
        if (actual_id <= 0 or media and media != actual_media
                or trakt_id is not None and trakt_id != actual_id
                or kind and kind != actual_kind):
            return None
        return value
    except (ValueError, TypeError):
        return None


def valid_webp(data):
    return (isinstance(data, bytes) and 20 <= len(data) <= MAX_BYTES
            and data[:4] == b'RIFF' and data[8:12] == b'WEBP'
            and int.from_bytes(data[4:8], 'little') + 8 == len(data)
            and data[12:16] in {b'VP8 ', b'VP8L', b'VP8X'})


class ImageUnavailable(Exception):
    def __init__(self, status=503, retry_after=0):
        super().__init__('Artwork unavailable')
        self.status = status
        self.retry_after = retry_after


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def download_image(url, *, deadline, monotonic=time.monotonic, resolver=socket.getaddrinfo,
                   connection_factory=PinnedHTTPSConnection):
    if not trakt_image_url(url):
        raise ImageUnavailable()
    parsed = urlsplit(url)
    addresses = resolver(parsed.hostname, 443, type=socket.SOCK_STREAM)
    ips = {row[4][0] for row in addresses}
    # Pin the validated public destination, while TLS still verifies the CDN host.
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ImageUnavailable()
    address = sorted(ips, key=lambda ip: (':' in ip, ip))[0]
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise ImageUnavailable()
    connection = connection_factory(parsed.hostname, address, min(2.5, remaining))
    try:
        connection.request('GET', parsed.path, headers={'Accept': 'image/webp', 'User-Agent': 'Movelle/1.0'})
        response = connection.getresponse()
        if response.status != 200:  # Redirects are never followed.
            try:
                delay = min(86400, max(0, int(response.getheader('Retry-After', '0'))))
            except ValueError:
                delay = 0
            raise ImageUnavailable(response.status, delay)
        if response.getheader('Content-Type', '').split(';')[0].strip().lower() != 'image/webp':
            raise ImageUnavailable()
        declared = response.getheader('Content-Length')
        if declared is not None and not 20 <= int(declared) <= MAX_BYTES:
            raise ImageUnavailable()
        chunks, size = [], 0
        while True:
            if monotonic() >= deadline:
                raise ImageUnavailable()
            chunk = response.read(min(65536, MAX_BYTES + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                raise ImageUnavailable()
            chunks.append(chunk)
        data = b''.join(chunks)
        if declared is not None and len(data) != int(declared) or not valid_webp(data):
            raise ImageUnavailable()
        return data
    except ImageUnavailable:
        raise
    except (OSError, ValueError, http.client.HTTPException):
        raise ImageUnavailable() from None
    finally:
        connection.close()


@dataclass(frozen=True)
class CachedImage:
    data: bytes
    fetched: float

    @property
    def etag(self):
        return '"' + hashlib.sha256(self.data).hexdigest() + '"'


class ImageCache:
    def __init__(self, root=None, *, fetch=download_image, clock=time.time, monotonic=time.monotonic):
        self.root = Path(root) if root else Path(tempfile.gettempdir()) / 'movelle-trakt-images-v1'
        self.fetch, self.clock, self.monotonic = fetch, clock, monotonic
        self.lock, self.slots = Lock(), BoundedSemaphore(2)
        self.memory, self.inflight, self.failed = OrderedDict(), {}, {}
        self.memory_bytes = 0

    def _remember(self, key, image):
        with self.lock:
            old = self.memory.pop(key, None)
            self.memory_bytes -= len(old.data) if old else 0
            self.memory[key] = image
            self.memory_bytes += len(image.data)
            while self.memory_bytes > 24 * 1024**2 or len(self.memory) > 128:
                _, old = self.memory.popitem(last=False)
                self.memory_bytes -= len(old.data)

    def get(self, url):
        if not trakt_image_url(url):
            return None
        key, now = hashlib.sha256(url.encode()).hexdigest(), self.clock()
        path = self.root / (key + '.webp')
        with self.lock:
            image = self.memory.get(key)
            if image is not None:
                self.memory.move_to_end(key)
        if image is None:
            try:
                if not path.is_symlink() and path.stat().st_size <= MAX_BYTES:
                    data = path.read_bytes()
                    if valid_webp(data):
                        image = CachedImage(data, path.stat().st_mtime)
                        self._remember(key, image)
            except OSError:
                pass
        if image and now - image.fetched >= RETENTION:
            image = None
        if image and now - image.fetched < TTL:
            return image
        with self.lock:
            if self.failed.get(key, 0) > now:
                return image
            event = self.inflight.get(key)
            leader = event is None
            if leader:
                event = self.inflight[key] = Event()
        if not leader:
            event.wait(7)
            with self.lock:
                completed = self.memory.get(key)
            return completed if completed and now - completed.fetched < RETENTION else image
        deadline = self.monotonic() + 6
        acquired = self.slots.acquire(timeout=6)
        try:
            if not acquired:
                return image
            data = self.fetch(url, deadline=deadline)
            if not valid_webp(data):
                raise ImageUnavailable()
            completed = CachedImage(data, now)
            self._remember(key, completed)
            try:
                self.root.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=self.root, prefix='.image-', delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(data)
                try:
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
                # Only owned hash-named cache files are eligible for eviction.
                files = [p for p in self.root.glob('*.webp') if re.fullmatch(r'[a-f0-9]{64}\.webp', p.name) and not p.is_symlink()]
                total = sum(p.stat().st_size for p in files)
                for candidate in sorted(files, key=lambda p: p.stat().st_mtime):
                    if total <= 128 * 1024**2 and len(files) <= 256:
                        break
                    total -= candidate.stat().st_size
                    candidate.unlink(missing_ok=True)
                    files.remove(candidate)
            except OSError:
                pass  # The bounded in-memory cache still satisfies cache-before-serving.
            return completed
        except ImageUnavailable as error:
            with self.lock:
                self.failed[key] = now + max(error.retry_after, 6 * 3600 if error.status == 404 else 30)
                while len(self.failed) > 512:
                    self.failed.pop(next(iter(self.failed)))
            return image
        except (OSError, ValueError):
            with self.lock:
                self.failed[key] = now + 30
                while len(self.failed) > 512:
                    self.failed.pop(next(iter(self.failed)))
            return image
        finally:
            if acquired:
                self.slots.release()
            with self.lock:
                self.inflight.pop(key, None)
            event.set()
