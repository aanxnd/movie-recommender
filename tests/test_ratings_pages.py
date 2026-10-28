from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import database
from app.main import create_app
from test_api import api_paths


def test_ratings_metadata_pagination_preserves_unavailable_movies(api_paths):
    with TestClient(create_app(*api_paths)) as client:
        profile = client.post('/users').json()
        auth = {'Authorization': 'Bearer ' + profile['token']}
        # Simulate preserved legacy data from a larger catalog, without API quota bypass.
        with Session(client.app.state.engine) as session, session.begin():
            database.register_movies(session, range(1, 151))
            for movie in range(1, 151): database.save_rating(session, profile['id'], movie, 3.25)
        first = client.get(f"/users/{profile['id']}/ratings/details", headers=auth).json()
        assert len(first['items']) == 100 and first['total'] == 150 and first['next_after'] == 100
        assert first['items'][0]['available'] is True
        assert first['items'][5]['available'] is False
        assert first['items'][5]['rating'] == 3.25
        second = client.get(f"/users/{profile['id']}/ratings/details?after=100", headers=auth).json()
        assert len(second['items']) == 50 and second['next_after'] is None
        assert len({row['movie_id'] for row in first['items'] + second['items']}) == 150
        assert client.get(f"/users/{profile['id']}/ratings/details").status_code == 401
        lookup = client.post(f"/users/{profile['id']}/ratings/lookup", headers=auth, json={'movie_ids': [1, 150]}).json()
        assert len(lookup) == 2 and lookup[1]['available'] is False
