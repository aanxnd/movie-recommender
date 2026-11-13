"""Real staging FastAPI + disposable PostgreSQL; Auth responses/signatures are synthetic."""
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import provisioning_principal, security, supabase_auth
from app.main import create_app
from app.models import Credential, User, UserIdentity
from app.staging import create_staging_app, ORIGIN
from app.staging_database import local_staging_url
from test_api import api_paths
from test_postgresql_concurrency import pg_engine
from test_supabase_claims import evidence
from test_supabase_policy import account


@pytest.fixture
def staging(pg_engine, api_paths, account, monkeypatch):
    e, policy, user, _ = account
    user['factors'] = [dict(id=str(uuid4()), factor_type='totp', status='verified')]
    monkeypatch.setattr(supabase_auth, 'SupabaseAccessPolicy', lambda **_: policy)
    monkeypatch.setattr(provisioning_principal, 'SupabaseAccessPolicy', lambda **_: policy)
    monkeypatch.setattr(security, 'authenticate', lambda *_: pytest.fail('Legacy fallback'))
    app = create_staging_app(prepared_dir=api_paths[0], database_url=pg_engine.url.render_as_string(hide_password=False),
        project_url=policy._verifier.issuer.removesuffix('/auth/v1'), publishable_key='sb_publishable_offline')
    with TestClient(app) as client:
        yield client, e, user, pg_engine


def headers(e, **claims):
    return {'Authorization': 'Bearer ' + e.sign({'aal': 'aal2', **claims}), 'Origin': ORIGIN}


def create(client, e, name='MovieFan'):
    response = client.post('/auth/profile', headers=headers(e), json={'username': name})
    assert response.status_code == 200 and response.json()['username'] == name
    return client.get('/users/me', headers=headers(e)).json()['id']


def test_real_public_app_never_creates_users_or_exposes_legacy_issuance(staging):
    client, e, _, engine = staging
    assert client.get('/health').json() == client.get('/ready').json() == {'status': 'ok'}
    assert client.get('/movies/search?q=Film').status_code == 200
    assert client.get('/recommendations/popular?min_rating_count=1').status_code == 200
    assert client.post('/users').status_code == 404
    assert client.get('/users/me').status_code == 401
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0
        assert session.scalar(select(func.count()).select_from(Credential)) == 0
    assert '/users' not in client.get('/openapi.json').json()['paths']
    assert client.get('/health', headers={'Origin': 'https://foreign.invalid'}).status_code == 403


def test_native_profile_ratings_and_numeric_ownership(staging):
    client, e, user, engine = staging
    uid = create(client, e)
    assert client.put(f'/users/{uid}/ratings/1', headers=headers(e), json={'rating': 4}).status_code == 200
    assert client.get(f'/users/{uid}/ratings', headers=headers(e)).json() == [{'user_id': uid, 'movie_id': 1, 'rating': 4}]
    page = client.get(f'/users/{uid}/ratings/details', headers=headers(e)).json()
    assert page['items'][0]['title'] == 'First Film' and page['total'] == 1
    assert len(client.post(f'/users/{uid}/ratings/lookup', headers=headers(e), json={'movie_ids': [1, 2]}).json()) == 1
    other = uuid4(); user['id'] = str(other)
    own = headers(e, sub=str(other))
    assert client.post('/auth/profile', headers=own, json={'username': 'OtherUser'}).status_code == 200
    for path in (f'/users/{uid}', f'/users/{uid}/ratings', f'/users/{uid}/ratings/details'):
        assert client.get(path, headers=own).status_code == 404
    assert client.put(f'/users/{uid}/ratings/1', headers=own, json={'rating': 1}).status_code == 404
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Credential)) == 0
        assert session.get(UserIdentity, uid).supabase_subject == e.subject


@pytest.mark.parametrize('changes', [{'exp': 1}, {'iss': 'https://wrong.invalid/auth/v1'}, {'aud': 'wrong'}])
def test_signed_invalid_identity_cannot_enter_staging(staging, changes):
    client, e, _, _ = staging
    assert client.get('/users/me', headers=headers(e, **changes)).status_code == 401


def test_policy_blockers_and_no_mixed_authentication(staging):
    client, e, user, _ = staging
    assert client.post('/auth/profile', headers=headers(e, aal='aal1'), json={'username': 'Alice'}).status_code == 401
    user['factors'] = []
    assert client.post('/auth/profile', headers=headers(e), json={'username': 'Alice'}).status_code == 401
    assert client.get('/users/me', headers={'Authorization': 'Bearer ' + 'a' * 43}).status_code == 401


def test_staging_keeps_bounded_middleware_and_native_artwork(staging):
    client, e, _, _ = staging
    assert client.post('/auth/profile', content=b'x' * 16385).status_code == 413
    response = client.options('/auth/profile', headers={'Origin': ORIGIN, 'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Authorization,Content-Type'})
    assert response.headers['access-control-allow-origin'] == ORIGIN
    assert client.post('/movies/artwork', json={'movie_ids': [1]}).status_code == 200
    assert client.post('/movies/artwork', json={'movie_ids': [1], 'personal_key': 'a' * 32}).status_code == 401
    create(client, e)
    assert client.post('/movies/artwork', headers=headers(e), json={'movie_ids': [1], 'personal_key': 'a' * 32}).status_code == 200


@pytest.mark.parametrize('url', ['sqlite:///local.db', 'postgresql://x:y@remote.invalid/movelle_staging_x',
    'postgresql://x:y@127.0.0.1/production', 'postgresql://x:y@127.0.0.1/movelle_staging_x?host=remote.invalid',
    'postgresql://x:y@127.0.0.1/movelle_staging_x?hostaddr=192.0.2.1',
    'postgresql://x:y@127.0.0.1/movelle_staging_x?options=-c%20search_path=public'])
def test_no_hosted_or_production_database_destination(url):
    with pytest.raises(ValueError, match='Explicit disposable loopback'): local_staging_url(url)


def test_production_factory_stays_legacy_only(api_paths, monkeypatch):
    monkeypatch.setattr(supabase_auth, 'make_supabase_auth_dependency', lambda **_: pytest.fail('Native activation'))
    with TestClient(create_app(*api_paths)) as client:
        assert client.post('/users').status_code == 201
        assert client.get('/auth/profile').status_code == 404


def test_staging_never_automatically_upgrades_an_old_schema(pg_engine, api_paths):
    from app.models import SchemaVersion
    with Session(pg_engine) as session, session.begin(): session.get(SchemaVersion, 1).version = 2
    application = create_staging_app(prepared_dir=api_paths[0], database_url=pg_engine.url.render_as_string(hide_password=False),
        project_url='https://' + 'a' * 20 + '.supabase.co', publishable_key='sb_publishable_offline')
    with pytest.raises(ValueError, match='migration required'):
        with TestClient(application): pass
    with Session(pg_engine) as session: assert session.get(SchemaVersion, 1).version == 2
