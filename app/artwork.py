"""Catalogue-only Trakt metadata and Fanart.tv artwork; MovieLens IDs stay canonical."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
from threading import Event, Lock
import time
import unicodedata
from urllib.parse import urlsplit

from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel, Field, SecretStr, field_validator
from sqlalchemy.orm import Session
from app import limits, security
from app.providers import ProviderClient, ProviderFailure
from app.schemas import UserId

router = APIRouter()
IMDB = re.compile(r'^tt[0-9]{7,10}$')
IMAGE_PATH = re.compile(r'^/fanart/[A-Za-z0-9/_-]+\.(?:jpg|png|webp)$')
SCHEMA = 'trakt-fanart-v1'


def film_name(title):
    match = re.search(r'\s*\((\d{4})\)\s*$', title)
    return (title[:match.start()] if match else title, int(match[1]) if match else None)


def normalized_title(title):
    article = re.match(r'^(.*),\s*(The|An|A)$', title, flags=re.I)
    if article:
        title = article[2] + ' ' + article[1]
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode().lower())


def title_variants(title):
    primary = re.sub(r'\s*\([^)]*\)', '', title).strip()
    aliases = re.findall(r'\((?:a\.k\.a\.\s*)?([^)]*)\)', title, flags=re.I)
    return {value for s in [primary, *aliases] if (value := normalized_title(s))}


def image_url(value):
    if not isinstance(value, str) or len(value) > 500:
        return None
    try:
        p = urlsplit(value)
        return value if (p.scheme == 'https' and p.netloc == 'assets.fanart.tv'
                         and not p.query and not p.fragment and IMAGE_PATH.fullmatch(p.path)
                         and '..' not in p.path) else None
    except ValueError:
        return None


def credit_url(value):
    if not isinstance(value, str) or len(value) > 500:
        return None
    try:
        p = urlsplit(value)
        return value if (p.scheme == 'https' and p.hostname and not p.username and not p.password
                         and not p.query and not p.fragment) else None
    except ValueError:
        return None


def select_image(rows, kind):
    choices = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not image_url(row.get('url')):
            continue
        try:
            width, height = int(row['width']), int(row['height'])
            likes = max(0, int(row.get('likes', 0)))
            if not (100 <= width <= 12000 and 100 <= height <= 12000):
                continue
            ratio = width / height
            if not (.55 <= ratio <= .85 if kind == 'poster' else 1.5 <= ratio <= 2.5):
                continue
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
        lang = row.get('lang', '')
        preference = 0 if lang == 'en' else 1 if lang in ('', '00') else 2
        item = {'url': row['url'], 'width': width, 'height': height,
                'copyright': str(row.get('copyright') or 'Unknown')[:300],
                'copyright_link': credit_url(row.get('copyright_link'))}
        choices.append(((preference, -likes, -width * height, str(row.get('id', '')), row['url']), item))
    return min(choices, key=lambda choice: choice[0])[1] if choices else None


class ArtworkLookup(BaseModel):
    movie_ids: list[UserId] = Field(min_length=1, max_length=8)
    personal_key: SecretStr | None = None
    include_credits: bool = False

    @field_validator('personal_key')
    @classmethod
    def valid_personal_key(cls, value):
        if value is not None and not re.fullmatch(r'[A-Fa-f0-9]{32}', value.get_secret_value()):
            raise ValueError('Invalid personal key')
        return value


class ArtworkStore:
    def __init__(self, catalog, *, trakt_id='', fanart_key='', links=None, cache=None,
                 fetch=None, clock=time.time, monotonic=time.monotonic):
        self.catalog, self.clock, self.monotonic = catalog, clock, monotonic
        self.client = ProviderClient(trakt_id, fanart_key, clock=clock, monotonic=monotonic)
        self.fetch = fetch or self.client.fetch
        self.trakt_id, self.fanart_key = trakt_id, fanart_key
        self.cache = Path(cache) / SCHEMA if cache else None
        self.memory, self.ids, self.inflight = OrderedDict(), {}, {}
        self.lock = Lock()
        if links:
            try:
                source = Path(links)
                with source.with_name('movies.csv').open(encoding='utf-8-sig', newline='') as f:
                    titles = {int(r['movieId']): r['title'] for r in csv.DictReader(f)}
                with source.open(encoding='utf-8-sig', newline='') as f:
                    for row in csv.DictReader(f):
                        mid, value = int(row['movieId']), row.get('imdbId') or ''
                        if not value.isdigit() or int(value) <= 0:
                            continue
                        imdb = 'tt' + value.zfill(7)
                        if mid in catalog and titles.get(mid) == catalog[mid].title and IMDB.fullmatch(imdb):
                            self.ids[mid] = imdb
            except (OSError, ValueError, KeyError, csv.Error):
                self.ids = {}

    @staticmethod
    def _valid_cached_item(layer, item):
        if item is None:
            return True
        if layer == 'credits':
            return isinstance(item, str) and len(item) <= 300
        if not isinstance(item, dict):
            return False
        if layer == 'metadata':
            return (isinstance(item.get('imdb_id'), str) and bool(IMDB.fullmatch(item['imdb_id']))
                    and type(item.get('trakt_id')) is int and item['trakt_id'] > 0
                    and isinstance(item.get('overview'), str)
                    and (item.get('runtime') is None or type(item['runtime']) is int)
                    and (item.get('released') is None or isinstance(item['released'], str))
                    and isinstance(item.get('metadata_genres', []), list)
                    and all(isinstance(g, str) for g in item.get('metadata_genres', [])))
        return all(row is None or (isinstance(row, dict) and image_url(row.get('url'))
                                  and type(row.get('width')) is int and type(row.get('height')) is int
                                  and isinstance(row.get('copyright'), str)
                                  and (row.get('copyright_link') is None or credit_url(row['copyright_link'])))
                   for row in (item.get('poster'), item.get('backdrop')))

    def _cached(self, layer, mid, resolve, *, scope='', ttl=7 * 86400, deadline=None):
        key = (layer, mid, scope)
        now = self.clock()
        with self.lock:
            entry = self.memory.get(key)
        path = self.cache / layer / f'{mid}.json' if self.cache and not scope else None
        if entry is None and path:
            try:
                with path.open('rb') as stream:
                    raw = stream.read(128001)
                if len(raw) <= 128000:
                    candidate = json.loads(raw)
                    if (candidate.get('schema') == SCHEMA and candidate.get('movie_id') == mid
                            and candidate.get('title') == self.catalog[mid].title
                            and isinstance(candidate.get('fetched_at'), (int, float))
                            and isinstance(candidate.get('expires'), (int, float))
                            and math.isfinite(candidate['fetched_at']) and math.isfinite(candidate['expires'])
                            and self._valid_cached_item(layer, candidate.get('item'))):
                        entry = candidate
            except (OSError, ValueError, TypeError, AttributeError):
                pass
        retention = 600 if scope else 30 * 86400
        if entry and now - entry['fetched_at'] >= retention:
            entry = None
            if path:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
        if entry and entry['expires'] > now:
            return entry.get('item')
        with self.lock:
            event = self.inflight.get(key)
            leader = event is None
            if leader:
                event = self.inflight[key] = Event()
        if not leader:
            event.wait(max(0, min(8, deadline - self.monotonic())) if deadline else 8)
            with self.lock:
                completed = self.memory.get(key)
            return (completed or entry or {}).get('item')
        try:
            item = resolve()
            lifetime = min(ttl, 600) if scope else ttl
            if not item:
                lifetime = 60 if scope else 6 * 3600
            record = {'schema': SCHEMA, 'movie_id': mid, 'title': self.catalog[mid].title,
                      'fetched_at': now, 'expires': now + lifetime, 'item': item}
            with self.lock:
                self.memory[key] = record
                self.memory.move_to_end(key)
                while len(self.memory) > 2048:
                    self.memory.popitem(last=False)
            if path:
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
                except OSError:
                    pass
            return item
        except ProviderFailure:
            return (entry or {}).get('item')  # Never negative-cache transport/auth errors.
        finally:
            with self.lock:
                self.inflight.pop(key, None)
            event.set()

    def _metadata(self, mid, deadline):
        title, year = film_name(self.catalog[mid].title)
        imdb = self.ids.get(mid)
        expected_tid = None
        if imdb:
            data = self.fetch('trakt', 'movies/' + imdb, {'extended': 'full'}, deadline=deadline)
            method = 'movielens_imdb'
        else:
            if year is None:
                return None
            query = re.sub(r'\s*\([^)]*\)', '', title).strip()
            article = re.match(r'^(.*),\s*(The|An|A)$', query, flags=re.I)
            if article:
                query = article[2] + ' ' + article[1]
            results = self.fetch('trakt', 'search/movie', {'query': query[:120], 'extended': 'full', 'limit': 10}, deadline=deadline)
            matches = {}
            for result in results if isinstance(results, list) else []:
                row = result.get('movie', {}) if isinstance(result, dict) and result.get('type') == 'movie' else {}
                if not isinstance(row, dict):
                    continue
                if (row.get('year') == year and isinstance(row.get('title'), str)
                        and title_variants(title) & title_variants(row['title'])):
                    ids = row.get('ids')
                    tid = ids.get('trakt') if isinstance(ids, dict) else None
                    if type(tid) is int and tid > 0:
                        matches[tid] = row
            if len(matches) != 1:
                return None
            tid = next(iter(matches))
            expected_tid = tid
            data = self.fetch('trakt', f'movies/{tid}', {'extended': 'full'}, deadline=deadline)
            method = 'exact_title_year'
        if not isinstance(data, dict):
            return None
        ids = data.get('ids')
        if not isinstance(ids, dict):
            return None
        matched_imdb, tid = ids.get('imdb'), ids.get('trakt')
        if (not isinstance(matched_imdb, str) or not IMDB.fullmatch(matched_imdb)
                or type(tid) is not int or tid <= 0
                or (expected_tid is not None and tid != expected_tid)
                or (imdb and matched_imdb != imdb)
                or (year and (type(data.get('year')) is not int or abs(data['year'] - year) > (1 if imdb else 0)))
                or (not imdb and not title_variants(title) & title_variants(str(data.get('title', ''))))):
            return None
        runtime, released = data.get('runtime'), data.get('released')
        return {'imdb_id': matched_imdb, 'trakt_id': tid, 'match': method,
                'overview': str(data.get('overview') or '')[:3000],
                'metadata_genres': [g[:60] for g in data.get('genres', []) if isinstance(g, str)][:20] if isinstance(data.get('genres'), list) else [],
                'runtime': runtime if type(runtime) is int and 0 < runtime < 2000 else None,
                'released': released if isinstance(released, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', released) else None}

    def _images(self, imdb, personal_key, deadline):
        data = self.fetch('fanart', 'movies/' + imdb, {'source': 'imdb'}, personal_key=personal_key, deadline=deadline)
        if not isinstance(data, dict) or data.get('imdb_id') != imdb:
            return None
        return {'poster': select_image(data.get('movieposter'), 'poster'),
                'backdrop': select_image(data.get('moviebackground'), 'backdrop')}

    def _credits(self, tid, deadline):
        data = self.fetch('trakt', f'movies/{tid}/people', deadline=deadline)
        crew = data.get('crew') if isinstance(data, dict) else None
        rows = crew.get('directing') if isinstance(crew, dict) else None
        names = set()
        for row in rows if isinstance(rows, list) else []:
            person = row.get('person') if isinstance(row, dict) else None
            if isinstance(row, dict) and row.get('job') == 'Director' and isinstance(person, dict) and isinstance(person.get('name'), str):
                names.add(person['name'][:100])
        return ', '.join(sorted(names))[:300] or None

    def get(self, mid, personal_key=None, include_credits=False):
        if mid not in self.catalog:
            return None
        deadline = self.monotonic() + 8
        meta = self._cached('metadata', mid, lambda: self._metadata(mid, deadline), deadline=deadline) if self.trakt_id else None
        imdb = (meta or {}).get('imdb_id') or self.ids.get(mid)
        if not imdb:
            return None
        scope = hashlib.sha256(personal_key.encode()).hexdigest() if personal_key else ''
        images = self._cached('images', mid, lambda: self._images(imdb, personal_key, deadline), scope=scope, deadline=deadline) if self.fanart_key else None
        director = self._cached('credits', mid, lambda: self._credits(meta['trakt_id'], deadline), deadline=deadline) if include_credits and meta and self.trakt_id else None
        if not meta and not images:
            return None
        poster, backdrop = (images or {}).get('poster'), (images or {}).get('backdrop')
        return {'movie_id': mid, **(meta or {'imdb_id': imdb, 'match': 'movielens_imdb'}),
                'poster_path': image_url((poster or {}).get('url')), 'backdrop_path': image_url((backdrop or {}).get('url')),
                'poster_credit': poster, 'backdrop_credit': backdrop, 'director': director,
                'credits_loaded': include_credits, 'source': 'trakt+fanart.tv'}

    def batch(self, ids, personal_key=None, include_credits=False):
        with ThreadPoolExecutor(max_workers=3) as pool:
            return [item for item in pool.map(lambda mid: self.get(mid, personal_key, include_credits), dict.fromkeys(ids)) if item]


@router.post('/movies/artwork')
def lookup_artwork(body: ArtworkLookup, request: Request, response: Response,
                   authorization: str | None = Header(default=None, max_length=100)):
    with Session(request.app.state.engine) as session, session.begin():
        host = request.client.host if request.client else 'unknown'
        limits.consume(session, host, 'artwork', 40, 60)
        limits.consume(session, 'all', 'artwork-global', 180, 60)
        if body.personal_key is not None:
            security.authenticate(session, authorization)
    response.headers['Cache-Control'] = 'no-store'
    store = request.app.state.artwork
    personal = body.personal_key.get_secret_value() if body.personal_key is not None else None
    return {'items': store.batch(body.movie_ids, personal, body.include_credits),
            'configured': bool(store.trakt_id and store.fanart_key), 'provider': 'trakt+fanart.tv'}


def configure(application):
    application.state.artwork = ArtworkStore(application.state.catalog,
        trakt_id=os.environ.get('TRAKT_CLIENT_ID', '').strip(),
        fanart_key=os.environ.get('FANART_API_KEY', '').strip(),
        links=os.environ.get('MOVELLE_ARTWORK_LINKS'), cache=os.environ.get('MOVELLE_ARTWORK_CACHE_DIR'))
