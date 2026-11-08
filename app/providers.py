"""Fixed-origin, bounded provider transport. Credentials are headers, never URLs."""
import hashlib
from collections import deque
import json
import math
import random
import time
from threading import BoundedSemaphore, Lock
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ProviderFailure(Exception):
    def __init__(self, status=503):
        super().__init__('Film provider unavailable')
        self.status = status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # Never forward credentials to a redirect destination.


class ProviderClient:
    def __init__(self, trakt_id='', fanart_key='', *, opener=None, clock=time.time,
                 monotonic=time.monotonic, sleep=time.sleep):
        self.trakt_id, self.fanart_key = trakt_id, fanart_key
        self.opener = opener or build_opener(NoRedirect()).open
        self.clock, self.monotonic, self.sleep = clock, monotonic, sleep
        self.lock, self.slots = Lock(), BoundedSemaphore(3)
        self.cooldowns, self.failures = {}, {}
        self.recent = {'trakt': deque(), 'fanart': deque()}
        self.budget = 200  # Per provider/process/five minutes; personal keys do not bypass it.

    def fetch(self, provider, path, params=None, personal_key=None, deadline=None):
        if provider not in {'trakt', 'fanart'}:
            raise ProviderFailure()
        key = self.trakt_id if provider == 'trakt' else self.fanart_key
        if not key:
            raise ProviderFailure()
        scope = (provider, hashlib.sha256((personal_key or '').encode()).hexdigest()
                 if provider == 'fanart' else '')
        with self.lock:
            if self.cooldowns.get(scope, 0) > self.clock():
                raise ProviderFailure(429)
        if not self.slots.acquire(blocking=False):
            raise ProviderFailure()
        deadline = deadline or self.monotonic() + 6
        try:
            headers = {'Accept': 'application/json', 'Content-Type': 'application/json', 'User-Agent': 'Movelle/1.0'}
            if provider == 'trakt':
                origin = 'https://api.trakt.tv/'
                headers.update({'trakt-api-key': key, 'trakt-api-version': '2'})
            else:
                origin = 'https://webservice.fanart.tv/v3.2/'
                headers['api-key'] = key
                if personal_key:
                    headers['client-key'] = personal_key
            query = urlencode(params or {})
            request = Request(origin + path + ('?' + query if query else ''), headers=headers)
            status, retry_after = 503, None
            for attempt in range(2):
                remaining = deadline - self.monotonic()
                if remaining <= 0:
                    break
                with self.lock:
                    recent = self.recent[provider]
                    while recent and recent[0] <= self.clock() - 300:
                        recent.popleft()
                    if len(recent) >= self.budget:
                        raise ProviderFailure(429)
                    recent.append(self.clock())
                try:
                    with self.opener(request, timeout=min(2.5, remaining)) as response:
                        raw = response.read(512_001)
                        if len(raw) > 512_000:
                            raise ProviderFailure()
                        data = json.loads(raw)
                        if not isinstance(data, (dict, list)):
                            raise ProviderFailure()
                    with self.lock:
                        self.failures.pop(scope, None)
                    return data
                except HTTPError as error:
                    status = error.code
                    retry_after = error.headers.get('Retry-After') if error.headers else None
                    error.close()
                    if status == 404:
                        return None
                    if status < 500:
                        break  # No authentication/rate-limit retries or bypass.
                except (OSError, ValueError):
                    status = 503
                if attempt == 0 and deadline - self.monotonic() > .3:
                    self.sleep(.1 + random.random() * .1)
            with self.lock:
                count = min(8, self.failures.get(scope, 0) + 1)
                self.failures[scope] = count
                delay = min(300, 2 ** count) + random.random()
                try:
                    requested = float(retry_after)
                    if math.isfinite(requested):
                        delay = max(delay, requested)
                except (TypeError, ValueError, OverflowError):
                    pass
                self.cooldowns[scope] = self.clock() + delay
                if len(self.cooldowns) > 256:
                    stale = [s for s, until in self.cooldowns.items() if until <= self.clock()]
                    for s in stale:
                        self.cooldowns.pop(s, None)
                        self.failures.pop(s, None)
                    while len(self.cooldowns) > 256:
                        stale = next(iter(self.cooldowns))
                        self.cooldowns.pop(stale)
                        self.failures.pop(stale, None)
            raise ProviderFailure(status) from None
        finally:
            self.slots.release()
