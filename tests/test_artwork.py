from concurrent.futures import ThreadPoolExecutor
import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.artwork import ArtworkStore, SCHEMA, normalized_title, select_image
from app.main import create_app
from app.providers import ProviderFailure
from test_api import api_paths


def catalog():
    return {1: SimpleNamespace(title='Matrix, The (1999)'), 2: SimpleNamespace(title='Other Film (2001)')}


def metadata(**extra):
    return {'ids': {'imdb': 'tt0133093', 'trakt': 481}, 'title': 'The Matrix', 'year': 1999,
            'released': '1999-03-31', 'runtime': 136, 'overview': 'A film synopsis.', 'genres': ['science-fiction'], **extra}


def image(name='poster', **extra):
    return {'id': '1', 'url': 'https://assets.fanart.tv/fanart/' + name + '.jpg',
            'width': '1000' if name == 'poster' else '1920', 'height': '1426' if name == 'poster' else '1080',
            'lang': 'en', 'likes': '4', 'copyright': 'Recorded studio', 'copyright_link': 'https://studio.example/credits', **extra}


def images(**extra):
    return {'imdb_id': 'tt0133093', 'movieposter': [image()], 'moviebackground': [image('backdrop')], **extra}


def links(tmp_path, title='Matrix, The (1999)'):
    (tmp_path / 'movies.csv').write_text('movieId,title,genres\n1,"' + title + '",Sci-Fi\n')
    (tmp_path / 'links.csv').write_text('movieId,imdbId\n1,0133093\n')
    return tmp_path / 'links.csv'


def fetcher(calls):
    def fetch(provider, path, params=None, **kw):
        calls.append((provider, path, params, kw.get('personal_key')))
        if provider == 'fanart': return images()
        if path.endswith('/people'): return {'crew': {'directing': [{'job': 'Director', 'person': {'name': 'A Director'}}]}}
        if path == 'search/movie': return [{'type': 'movie', 'movie': metadata()}]
        return metadata()
    return fetch


def store(tmp_path, calls, **kw):
    return ArtworkStore(catalog(), trakt_id='fixture-client', fanart_key='fixture-project',
                        links=links(tmp_path), fetch=fetcher(calls), **kw)


def test_imdb_identity_and_display_contract_do_not_change_movielens_ids(tmp_path):
    calls=[]; artwork=store(tmp_path,calls,cache=tmp_path/'cache')
    item=artwork.get(1)
    assert item['movie_id']==1 and item['imdb_id']=='tt0133093' and item['trakt_id']==481
    assert item['match']=='movielens_imdb' and item['runtime']==136
    assert item['metadata_genres']==['science-fiction']
    assert item['poster_path']=='https://assets.fanart.tv/fanart/poster.jpg'
    assert item['poster_credit']['copyright']=='Recorded studio'
    assert [(p,path) for p,path,*_ in calls]==[('trakt','movies/tt0133093'),('fanart','movies/tt0133093')]
    assert artwork.get(1)==item and len(calls)==2
    refreshed=store(tmp_path,[],cache=tmp_path/'cache')
    assert refreshed.get(1)==item
    assert ArtworkStore(catalog(),cache=tmp_path/'cache').get(1) is None


def test_credit_lookup_is_requested_only_when_details_are_opened(tmp_path):
    calls=[]; artwork=store(tmp_path,calls)
    assert artwork.get(1)['director'] is None
    assert artwork.get(1,include_credits=True)['director']=='A Director'
    assert artwork.get(1,include_credits=True)['director']=='A Director'
    assert sum(path.endswith('/people') for _,path,*_ in calls)==1


def test_verified_links_require_matching_catalogue_and_safe_title_year_fallback(tmp_path):
    calls=[]
    artwork=ArtworkStore(catalog(),trakt_id='fixture',fanart_key='fixture',
                         links=links(tmp_path,'Wrong Film (1999)'),fetch=fetcher(calls))
    assert artwork.get(1)['match']=='exact_title_year'
    assert calls[0][1]=='search/movie'
    assert normalized_title('Matrix, The')==normalized_title('The Matrix')


@pytest.mark.parametrize('rows',[[],[metadata(year=2000)],[metadata(),metadata(ids={'imdb':'tt9999999','trakt':99})]])
def test_missing_wrong_year_and_ambiguous_search_never_assign_wrong_art(rows):
    def fetch(*a,**kw): return [{'type':'movie','movie':row} for row in rows]
    artwork=ArtworkStore(catalog(),trakt_id='fixture',fanart_key='fixture',fetch=fetch)
    assert artwork.get(1) is None


def test_alternate_title_matching_is_exact_and_wrong_id_is_rejected(tmp_path):
    def fetch(provider,path,*a,**kw):
        if provider=='fanart': return images()
        row=metadata(title='The Matrix')
        return [{'type':'movie','movie':row}] if path=='search/movie' else row
    movies={1:SimpleNamespace(title='Other (a.k.a. The Matrix) (1999)')}
    assert ArtworkStore(movies,trakt_id='fixture',fanart_key='fixture',fetch=fetch).get(1)['imdb_id']=='tt0133093'
    artwork=store(tmp_path,[])
    artwork.fetch=lambda *a,**kw: metadata(ids={'imdb':'tt0000001','trakt':99}) if a[0]=='trakt' else images(imdb_id='tt0000001')
    assert artwork.get(1) is None


def test_deterministic_geometry_language_likes_and_copyright_selection():
    options=[image(id='2',lang='fr',likes='100'),image(id='3',likes='9'),image(id='1',likes='9'),image(url='https://evil.invalid/poster.jpg')]
    assert select_image(options,'poster')==select_image(list(reversed(options)),'poster')
    assert select_image(options,'poster')['url'].startswith('https://assets.fanart.tv/')
    assert select_image([image(width='1000',height='100')],'poster') is None
    assert select_image([image(url='https://assets.fanart.tv/fanart/../secret.jpg')],'poster') is None
    assert select_image([image(copyright_link='javascript:alert(1)')],'poster')['copyright_link'] is None


def test_missing_artwork_and_sparse_metadata_are_honest_and_negative_cached(tmp_path):
    calls=[]
    def fetch(provider,*a,**kw):
        calls.append(provider)
        return metadata(overview=None,runtime=None,released=None) if provider=='trakt' else None
    artwork=store(tmp_path,[]);artwork.fetch=fetch
    item=artwork.get(1)
    assert item['poster_path'] is None and item['backdrop_path'] is None and item['runtime'] is None
    assert artwork.get(1)==item and calls==['trakt','fanart']
    assert artwork.get(999) is None


def test_personal_images_are_isolated_ephemeral_and_never_persist_keys(tmp_path):
    calls=[]; artwork=store(tmp_path,calls,cache=tmp_path/'cache')
    ordinary=artwork.get(1)
    original=artwork.fetch
    def personal(provider,*a,**kw):
        if provider=='fanart' and kw.get('personal_key'):
            calls.append(('fanart','personal',None,kw['personal_key']))
            return images(movieposter=[image(url='https://assets.fanart.tv/fanart/new.jpg')])
        return original(provider,*a,**kw)
    artwork.fetch=personal
    personal_key='a'*32
    assert artwork.get(1,personal_key)['poster_path'].endswith('/new.jpg')
    assert artwork.get(1)['poster_path']==ordinary['poster_path']
    assert artwork.get(1,'b'*32)['poster_path'].endswith('/new.jpg')
    serialized=''.join(p.read_text() for p in (tmp_path/'cache').rglob('*.json'))
    assert personal_key not in serialized and 'new.jpg' not in serialized
    assert len([c for c in calls if c[1]=='personal'])==2


def test_fresh_expired_stale_and_legacy_cache_boundaries(tmp_path):
    now=[100.];calls=[];artwork=store(tmp_path,calls,cache=tmp_path/'cache',clock=lambda:now[0])
    first=artwork.get(1)
    now[0]+=8*86400
    def unavailable(*a,**kw): raise ProviderFailure()
    artwork.fetch=unavailable
    assert artwork.get(1)==first
    now[0]+=31*86400
    assert artwork.get(1) is None
    legacy=tmp_path/'legacy';legacy.mkdir();(legacy/'1.json').write_text(json.dumps({'item':first,'expires':now[0]+100000}))
    replacement=store(tmp_path,[],cache=legacy);replacement.fetch=unavailable
    assert replacement.get(1) is None and (legacy/'1.json').exists()


def test_simultaneous_requests_share_each_upstream_lookup(tmp_path):
    calls=[];artwork=store(tmp_path,calls)
    original=artwork.fetch
    def slow(*a,**kw): time.sleep(.02);return original(*a,**kw)
    artwork.fetch=slow
    with ThreadPoolExecutor(max_workers=8) as pool: results=list(pool.map(artwork.get,[1]*8))
    assert all(r==results[0] for r in results) and len(calls)==2


def test_artwork_endpoint_is_catalogue_only_bounded_no_store_and_personal_authenticated(api_paths):
    with TestClient(create_app(*api_paths)) as client:
        result=client.post('/movies/artwork',json={'movie_ids':[1]})
        assert result.status_code==200 and result.json()['items']==[]
        assert result.headers['Cache-Control']=='no-store'
        for ids in [[],list(range(1,10)),[True],[0],['1']]:
            assert client.post('/movies/artwork',json={'movie_ids':ids}).status_code==422
        key='a'*32
        assert client.post('/movies/artwork',json={'movie_ids':[1],'personal_key':key}).status_code==401
        user=client.post('/users').json()
        result=client.post('/movies/artwork',json={'movie_ids':[1],'personal_key':key},headers={'Authorization':'Bearer '+user['token']})
        assert result.status_code==200 and key not in result.text
        invalid=client.post('/movies/artwork',json={'movie_ids':[1],'personal_key':{'password':key}})
        assert invalid.status_code==422 and key not in invalid.text
        assert set(invalid.json()['detail'][0])=={'type','loc','msg'}


def test_artwork_has_its_own_quota_in_addition_to_general_admission(api_paths):
    with TestClient(create_app(*api_paths)) as client:
        for _ in range(40): assert client.post('/movies/artwork',json={'movie_ids':[1]}).status_code==200
        result=client.post('/movies/artwork',json={'movie_ids':[1]})
        assert result.status_code==429 and result.headers.get('Retry-After')


def test_search_summary_must_confirm_requested_trakt_id_and_empty_transliterations_do_not_match():
    def fetch(provider,path,*a,**kw):
        if path=='search/movie': return [{'type':'movie','movie':metadata()}]
        return metadata(ids={'imdb':'tt0133093','trakt':999})
    assert ArtworkStore(catalog(),trakt_id='fixture',fanart_key='fixture',fetch=fetch).get(1) is None
    movies={1:SimpleNamespace(title='\u6771\u4eac (1999)')}
    def unrelated(*a,**kw): return [{'type':'movie','movie':metadata(title='\u4eac\u90fd')}]
    assert ArtworkStore(movies,trakt_id='fixture',fanart_key='fixture',fetch=unrelated).get(1) is None


def test_invalid_cache_shapes_never_become_provider_paths_or_rendered_metadata(tmp_path):
    calls=[];artwork=store(tmp_path,calls,cache=tmp_path/'cache')
    artwork.get(1)
    for layer,bad in [('metadata',{'imdb_id':'../../other','trakt_id':481}),('images',{'poster':'not-an-image-object'})]:
        path=tmp_path/'cache'/SCHEMA/layer/'1.json'
        record=json.loads(path.read_text(encoding='utf-8'));record['item']=bad
        path.write_text(json.dumps(record),encoding='utf-8')
    calls.clear()
    fresh=store(tmp_path,calls,cache=tmp_path/'cache')
    assert fresh.get(1)['imdb_id']=='tt0133093'
    assert [(p,path) for p,path,*_ in calls]==[('trakt','movies/tt0133093'),('fanart','movies/tt0133093')]


def test_duplicate_waits_share_the_same_film_deadline(tmp_path):
    now=[100.]; waits=[];artwork=store(tmp_path,[],monotonic=lambda:now[0])
    class Pending:
        def wait(self,seconds):waits.append(seconds);now[0]+=seconds
    artwork.inflight[('metadata',1,'')]=Pending()
    artwork.inflight[('images',1,'')]=Pending()
    assert artwork.get(1) is None
    assert waits==[8,0]


def test_missing_imdb_cell_is_ignored_without_breaking_startup(tmp_path):
    source=links(tmp_path)
    source.write_text('movieId,imdbId\n1\n',encoding='utf-8')
    artwork=ArtworkStore(catalog(),trakt_id='fixture',fanart_key='fixture',links=source,fetch=fetcher([]))
    assert artwork.ids=={} and artwork.get(1)['match']=='exact_title_year'
