"""Full staging HTTP authorization/computation with real PostgreSQL, simulated Auth."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import security
from app.models import Credential, User, UserRating
from test_api import api_paths
from test_postgresql_concurrency import pg_engine
from test_supabase_claims import evidence
from test_supabase_policy import account
from test_staging_app import staging, headers, create


def test_numeric_personal_recommendations_and_group_consent(staging):
    client, e, user, engine = staging
    uid = create(client, e)
    auth = headers(e)
    for mid, rating in [(1, 1), (2, 5)]:
        assert client.put(f'/users/{uid}/ratings/{mid}', headers=auth, json={'rating': rating}).status_code == 200
    response = client.get(f'/users/{uid}/recommendations?min_rating_count=1', headers=auth)
    assert response.status_code == 200 and response.json()
    assert all(row['movie_id'] not in {1, 2} for row in response.json())
    other = uuid4(); user['id'] = str(other)
    other_auth = headers(e, sub=str(other))
    assert client.post('/auth/profile', headers=other_auth, json={'username': 'PeerUser'}).status_code == 200
    peer = client.get('/users/me', headers=other_auth).json()['id']
    assert client.put(f'/users/{peer}/ratings/3', headers=other_auth, json={'rating': 4}).status_code == 200
    grant = client.post(f'/users/{peer}/group-invitation', headers=other_auth).json()['code'].split(':')[1]
    user['id'] = str(e.subject)
    body = {'user_ids': [uid, peer], 'invitations': {str(peer): grant}}
    result = client.post('/recommendations/group?min_rating_count=1', headers=auth, json=body)
    assert result.status_code == 200
    assert all(row['movie_id'] not in {1, 2, 3} for row in result.json())
    assert client.get(f'/users/{peer}/ratings', headers=auth).status_code == 404
    assert client.get(f'/users/{peer}/recommendations', headers=auth).status_code == 404
    body['invitations'][str(peer)] = 'x' * 43
    assert client.post('/recommendations/group', headers=auth, json=body).status_code == 404
    user['id'] = str(other)
    assert client.delete(f'/users/{peer}/group-invitation', headers=other_auth).status_code == 204
    user['id'] = str(e.subject); body['invitations'][str(peer)] = grant
    assert client.post('/recommendations/group', headers=auth, json=body).status_code == 404
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRating)) == 3
        assert session.scalar(select(func.count()).select_from(Credential)) == 0


def test_parallel_http_provisioning_uses_one_numeric_profile(staging):
    client, e, _, engine = staging
    auth = headers(e)
    def create_one(name):
        return client.post('/auth/profile', headers=auth, json={'username': name})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create_one, ['FirstName', 'SecondName']))
    assert all(r.status_code == 200 for r in responses)
    assert responses[0].json() == responses[1].json()
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1


def test_bad_rating_rolls_back_and_rate_limits_still_apply(staging):
    client, e, _, engine = staging
    uid = create(client, e); auth = headers(e)
    assert client.put(f'/users/{uid}/ratings/1', headers=auth, json={'rating': 'private'}).status_code == 422
    assert client.put(f'/users/{uid}/ratings/999', headers=auth, json={'rating': 4}).status_code == 404
    for _ in range(6):
        assert client.get(f'/users/{uid}/recommendations', headers=auth).status_code == 200
    response = client.get(f'/users/{uid}/recommendations', headers=auth)
    assert response.status_code == 429 and response.headers['retry-after']
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRating)) == 0
