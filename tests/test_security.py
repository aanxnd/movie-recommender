import time

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import database, security
from app.main import create_app
from app.models import Credential, Movie, User, UserRating
from test_api import api_paths


def test_independent_clients_require_credentials_and_never_expose_them(api_paths):
    with TestClient(create_app(*api_paths)) as owner:
        created = owner.post('/users')
        profile = created.json()
        auth = {'Authorization': 'Bearer ' + profile['token']}
        assert created.headers['cache-control'] == 'no-store'
        with Session(owner.app.state.engine) as session:
            stored = session.get(Credential, profile['id'])
            assert stored.token_hash != profile['token']
            assert stored.token_hash == security.token_hash(profile['token'])
        for path in (f"/users/{profile['id']}", f"/users/{profile['id']}/ratings", f"/users/{profile['id']}/recommendations"):
            assert owner.get(path).status_code == 401
            assert owner.get(path, headers=auth).status_code == 200
        assert owner.put(f"/users/{profile['id']}/ratings/1", json={'rating': 4}).status_code == 401
        second = owner.post('/users').json()
        assert owner.get(f"/users/{profile['id']}", headers={'Authorization': 'Bearer ' + second['token']}).status_code == 403
        assert owner.get('/users/me', headers=auth).json() == {'id': profile['id']}
        with Session(owner.app.state.engine) as session, session.begin():
            session.get(Credential, profile['id']).expires_at = int(time.time()) - 1
        assert owner.get('/users/me', headers=auth).status_code == 401


def test_group_capabilities_are_scoped_expiring_and_revocable(api_paths):
    with TestClient(create_app(*api_paths)) as client:
        a, b = client.post('/users').json(), client.post('/users').json()
        auth_a = {'Authorization': 'Bearer ' + a['token']}
        auth_b = {'Authorization': 'Bearer ' + b['token']}
        body = {'user_ids': [a['id'], b['id']]}
        assert client.post('/recommendations/group', headers=auth_a, json=body).status_code == 403
        grant = client.post(f"/users/{b['id']}/group-invitation", headers=auth_b).json()
        body['invitations'] = {str(b['id']): grant['code'].split(':')[1]}
        assert client.post('/recommendations/group', headers=auth_a, json=body).status_code == 200
        assert client.get(f"/users/{b['id']}/ratings", headers={'Authorization': 'Bearer ' + body['invitations'][str(b['id'])]}).status_code == 401
        client.delete(f"/users/{b['id']}/group-invitation", headers=auth_b)
        assert client.post('/recommendations/group', headers=auth_a, json=body).status_code == 403


def test_additive_migration_preserves_legacy_data_and_leaves_it_locked(tmp_path):
    engine = database.create_database_engine(tmp_path / 'legacy.db')
    try:
        with engine.begin() as connection:
            for table in (User.__table__, Movie.__table__, UserRating.__table__):
                table.create(connection)
            connection.execute(User.__table__.insert().values(id=42))
            connection.execute(Movie.__table__.insert().values(movie_id=1))
            connection.execute(UserRating.__table__.insert().values(user_id=42, movie_id=1, rating=3.25))
        database.create_schema(engine)
        database.create_schema(engine)
        with Session(engine) as session:
            assert database.get_user_profile(session, 42) == {1: 3.25}
            assert session.get(Credential, 42) is None
    finally:
        engine.dispose()
