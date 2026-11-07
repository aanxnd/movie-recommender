"""Optional, bounded TMDB metadata enrichment; MovieLens IDs remain canonical."""

import csv
import json
import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import BoundedSemaphore, Lock
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from fastapi import APIRouter, Request as ApiRequest
from pydantic import BaseModel, Field
from app.schemas import UserId

router = APIRouter()
IMAGE_PATH = re.compile(r"^/[A-Za-z0-9_-]+\.(?:jpg|png|webp)$")


def film_name(title):
    match = re.search(r"\s*\((\d{4})\)\s*$", title)
    return (title[:match.start()] if match else title, int(match[1]) if match else None)


def normalized_title(title):
    article = re.match(r"^(.*),\s*(The|An|A)$", title, flags=re.I)
    if article:
        title = article[2] + ' ' + article[1]
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode().lower())


class ArtworkLookup(BaseModel):
    movie_ids: list[UserId] = Field(min_length=1, max_length=8)


class ArtworkStore:
    def __init__(self, catalog, *, token='', links=None, cache=None, fetch=None, clock=time.time):
        self.catalog, self.token, self.cache = catalog, token, Path(cache) if cache else None
        self.clock, self.fetch = clock, fetch or self._fetch
        self.slots = BoundedSemaphore(3)
        self.memory, self.ids = {}, {}
        self.lock = Lock()
        self.cooldown = 0
        self.last_prune = 0
        self._prune()
        if links:
            # Never assume an arbitrary links.csv belongs to this catalogue.
            source = Path(links)
            try:
                with source.with_name('movies.csv').open(encoding='utf-8-sig', newline='') as stream:
                    titles = {int(row['movieId']): row['title'] for row in csv.DictReader(stream)}
                with source.open(encoding='utf-8-sig', newline='') as stream:
                    for row in csv.DictReader(stream):
                        mid = int(row['movieId'])
                        if mid in catalog and titles.get(mid) == catalog[mid].title and row.get('tmdbId', '').isdigit():
                            self.ids[mid] = int(row['tmdbId'])
            except (OSError, ValueError, KeyError):
                self.ids = {}

    def _prune(self):
        now = self.clock()
        if self.last_prune and now - self.last_prune < 86400:
            return
        self.last_prune = now
        with self.lock:
            expired = [mid for mid, entry in self.memory.items()
                       if now - entry.get('fetched_at', entry.get('expires', now) - 7 * 86400) >= 150 * 86400]
            for mid in expired:
                self.memory.pop(mid, None)
        if not self.cache or not self.cache.exists():
            return
        for source in self.cache.glob('*.json'):
            try:
                entry = json.loads(source.read_text(encoding='utf-8'))
                owned = source.stem.isdigit() and entry.get('movie_id') == int(source.stem) and isinstance(entry.get('expires'), (int, float))
                fetched = entry.get('fetched_at', entry.get('expires', now) - 7 * 86400)
                # Conservative retention below the provider's six-month ceiling.
                if owned and now - fetched >= 150 * 86400:
                    source.unlink()
            except (OSError, ValueError, TypeError, AttributeError):
                continue

    def _fetch(self, path, params=None):
        query = urlencode(params or {})
        req = Request('https://api.themoviedb.org/3/' + path + ('?' + query if query else ''),
                      headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json'})
        with urlopen(req, timeout=3) as response:
            # Bound metadata even if an upstream unexpectedly sends a huge body.
            body = response.read(512_001)
            if len(body) > 512_000:
                raise ValueError('Oversized metadata')
            return json.loads(body)

    def _read(self, mid):
        self._prune()
        with self.lock:
            entry = self.memory.get(mid)
        if entry is None and self.cache:
            try:
                entry = json.loads((self.cache / f'{mid}.json').read_text(encoding='utf-8'))
                if entry.get('movie_id') != mid or entry.get('title') != self.catalog[mid].title:
                    return None
            except (OSError, ValueError, TypeError, AttributeError):
                return None
        if entry and self.clock() - entry.get('fetched_at', entry.get('expires', 0) - 7 * 86400) >= 150 * 86400:
            with self.lock:
                self.memory.pop(mid, None)
            return None
        return entry

    def _save(self, mid, item, ttl):
        entry = {'movie_id': mid, 'title': self.catalog[mid].title, 'fetched_at': self.clock(), 'expires': self.clock() + ttl, 'item': item}
        with self.lock:
            self.memory[mid] = entry
            if self.cache:
                try:
                    self.cache.mkdir(parents=True, exist_ok=True)
                    temporary = self.cache / f'{mid}.tmp'
                    temporary.write_text(json.dumps(entry), encoding='utf-8')
                    temporary.replace(self.cache / f'{mid}.json')
                except OSError:
                    pass  # A read-only disk must not prevent browsing or ratings.

    def _resolve(self, mid):
        title, year = film_name(self.catalog[mid].title)
        tmdb_id = self.ids.get(mid)
        method = 'movielens_link'
        if not tmdb_id:
            if not year or not normalized_title(title):
                return None
            query = re.sub(r",\s*(The|An|A)$", lambda m: '', title, flags=re.I)
            candidates = self.fetch('search/movie', {'query': query, 'year': year, 'include_adult': 'false'}).get('results', [])
            matches = [row for row in candidates if row.get('release_date', '')[:4] == str(year) and
                       normalized_title(title) in {normalized_title(row.get('title', '')), normalized_title(row.get('original_title', ''))}]
            # Ambiguous names never select the first search result.
            if len(matches) != 1:
                return None
            tmdb_id, method = matches[0]['id'], 'exact_title_year'
        data = self.fetch(f'movie/{int(tmdb_id)}', {'append_to_response': 'credits'})
        release = data.get('release_date', '')
        if data.get('id') != tmdb_id or (year and (not release[:4].isdigit() or abs(int(release[:4]) - year) > 1)):
            return None
        poster, backdrop = data.get('poster_path'), data.get('backdrop_path')
        poster = poster if isinstance(poster, str) and IMAGE_PATH.fullmatch(poster) else None
        backdrop = backdrop if isinstance(backdrop, str) and IMAGE_PATH.fullmatch(backdrop) else None
        runtime = data.get('runtime')
        runtime = runtime if isinstance(runtime, int) and 0 < runtime < 2000 else None
        return {'movie_id': mid, 'tmdb_id': tmdb_id, 'poster_path': poster, 'backdrop_path': backdrop,
                'overview': str(data.get('overview') or '')[:3000], 'runtime': runtime,
                'director': ', '.join(row['name'] for row in data.get('credits', {}).get('crew', []) if row.get('job') == 'Director')[:180],
                'source': 'tmdb', 'match': method}

    def get(self, mid):
        if mid not in self.catalog:
            return None
        entry = self._read(mid)
        if entry and entry.get('expires', 0) > self.clock():
            return entry.get('item')
        if not self.token or self.clock() < self.cooldown or not self.slots.acquire(blocking=False):
            return entry.get('item') if entry else None
        try:
            item = self._resolve(mid)
            self._save(mid, item, 7 * 86400 if item else 6 * 3600)
            return item
        except HTTPError as error:
            if error.code == 429:
                try:
                    delay = min(300, max(1, int(error.headers.get('Retry-After', 60))))
                except (ValueError, TypeError):
                    delay = 60
                self.cooldown = self.clock() + delay
            return entry.get('item') if entry else None
        except (OSError, ValueError, TypeError, KeyError):
            # Preserve known imagery during outages; never cache a transport failure as a match.
            return entry.get('item') if entry else None
        finally:
            self.slots.release()

    def batch(self, ids):
        with ThreadPoolExecutor(max_workers=3) as pool:
            return [item for item in pool.map(self.get, dict.fromkeys(ids)) if item]


@router.post('/movies/artwork')
def lookup_artwork(body: ArtworkLookup, request: ApiRequest):
    store = request.app.state.artwork
    return {'items': store.batch(body.movie_ids), 'configured': bool(store.token), 'provider': 'tmdb'}


def configure(application):
    # Called after catalogue startup. No remote request occurs during readiness.
    application.state.artwork = ArtworkStore(application.state.catalog,
        token=os.environ.get('TMDB_READ_ACCESS_TOKEN', '').strip(),
        links=os.environ.get('MOVELLE_ARTWORK_LINKS'), cache=os.environ.get('MOVELLE_ARTWORK_CACHE_DIR'))
