from types import SimpleNamespace
from urllib.error import HTTPError

from app.artwork import ArtworkStore, normalized_title


def catalog():
    return {1: SimpleNamespace(title='Matrix, The (1999)'), 2: SimpleNamespace(title='Other Film (2001)')}


def details(tid=603, year='1999', **extra):
    return {'id': tid, 'release_date': year + '-03-30', 'poster_path': '/poster.jpg',
            'backdrop_path': '/backdrop.jpg', 'overview': 'A film synopsis.', 'runtime': 136,
            'credits': {'crew': [{'job': 'Director', 'name': 'A director'}]}, **extra}


def links(tmp_path, title='Matrix, The (1999)'):
    (tmp_path / 'movies.csv').write_text('movieId,title,genres\n1,"' + title + '",Sci-Fi\n', encoding='utf-8')
    (tmp_path / 'links.csv').write_text('movieId,imdbId,tmdbId\n1,0133093,603\n', encoding='utf-8')
    return tmp_path / 'links.csv'


def test_canonical_link_uses_id_and_does_not_search_or_change_movie_identity(tmp_path):
    calls = []
    def fetch(path, params):
        calls.append(path)
        return details()
    store = ArtworkStore(catalog(), token='local-test', links=links(tmp_path), cache=tmp_path / 'cache', fetch=fetch)
    item = store.get(1)
    assert item['movie_id'] == 1 and item['tmdb_id'] == 603 and item['match'] == 'movielens_link'
    assert calls == ['movie/603']
    assert store.get(1) == item and calls == ['movie/603']
    # A fresh process can use the public metadata cache without a credential.
    assert ArtworkStore(catalog(), cache=tmp_path / 'cache').get(1) == item
    assert 'local-test' not in (tmp_path / 'cache' / '1.json').read_text()


def test_mismatched_catalogue_links_are_ignored_and_exact_title_year_handles_articles(tmp_path):
    assert normalized_title('Matrix, The') == normalized_title('The Matrix')
    calls = []
    def fetch(path, params):
        calls.append(path)
        return {'results': [{'id': 603, 'title': 'The Matrix', 'release_date': '1999-03-30'}]} if path == 'search/movie' else details()
    item = ArtworkStore(catalog(), token='local-test', links=links(tmp_path, 'An Unrelated Film (1999)'), fetch=fetch).get(1)
    assert calls == ['search/movie', 'movie/603']
    assert item['match'] == 'exact_title_year'


def test_ambiguous_or_wrong_year_search_never_assigns_a_poster():
    for candidates in [[], [{'id': 1, 'title': 'The Matrix', 'release_date': '2000-01-01'}],
                       [{'id': n, 'title': 'The Matrix', 'release_date': '1999-01-01'} for n in (1, 2)]]:
        store = ArtworkStore(catalog(), token='local-test', fetch=lambda *_: {'results': candidates})
        assert store.get(1) is None


def test_upstream_paths_are_validated_and_release_mismatch_rejected(tmp_path):
    source = links(tmp_path)
    store = ArtworkStore(catalog(), token='local-test', links=source,
                         fetch=lambda *_: details(poster_path='https://attacker.example/image.jpg', backdrop_path='/../secret'))
    assert store.get(1)['poster_path'] is None and store.get(1)['backdrop_path'] is None
    store = ArtworkStore(catalog(), token='local-test', links=source, fetch=lambda *_: details(year='2010'))
    assert store.get(1) is None


def test_no_token_unknown_movies_and_unavailable_upstream_remain_optional(tmp_path):
    def unavailable(*_):
        raise OSError('Transport detail must not be exposed')
    assert ArtworkStore(catalog(), fetch=unavailable).get(1) is None
    store = ArtworkStore(catalog(), token='local-test', links=links(tmp_path), fetch=unavailable)
    assert store.batch([1, 1, 999]) == []
    assert store.get(999) is None


def test_expired_known_metadata_survives_an_outage_and_rate_limit_sets_cooldown(tmp_path):
    now = [100.0]
    store = ArtworkStore(catalog(), token='local-test', links=links(tmp_path), fetch=lambda *_: details(), clock=lambda: now[0])
    original = store.get(1)
    now[0] += 8 * 86400
    calls = []
    def busy(*_):
        calls.append(1)
        raise HTTPError('https://api.themoviedb.org', 429, 'Busy', {'Retry-After': '20'}, None)
    store.fetch = busy
    assert store.get(1) == original and store.get(1) == original
    assert calls == [1]


def test_artwork_batch_contract_is_bounded_and_preserves_normal_api(client):
    # Imported fixture is provided below; no remote traffic or credentials.
    result = client.post('/movies/artwork', json={'movie_ids': [1]})
    assert result.status_code == 200 and result.json()['items'] == []
    for ids in [[], list(range(1, 10)), [True], [0], ['1']]:
        assert client.post('/movies/artwork', json={'movie_ids': ids}).status_code == 422
    assert client.get('/health').json() == {'status': 'ok'}


def test_provider_retention_ceiling_removes_old_cache_even_during_outages(tmp_path):
    now = [100.0]
    store = ArtworkStore(catalog(), token='local-test', links=links(tmp_path), cache=tmp_path / 'cache',
                         fetch=lambda *_: details(), clock=lambda: now[0])
    assert store.get(1)
    unrelated = tmp_path / 'cache' / 'notes.json'
    unrelated.write_text('{"note":"preserve unrelated files"}')
    now[0] += 151 * 86400
    store.token = ''
    assert store.get(2) is None
    assert 1 not in store.memory
    assert store.get(1) is None
    assert not (tmp_path / 'cache' / '1.json').exists()
    assert unrelated.exists()


from test_api import client, api_paths  # Shared isolated prepared-data fixtures.
