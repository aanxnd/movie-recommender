from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import budget, database, limits
from app.main import create_app
from test_api import api_paths


def test_replica_engines_share_atomic_rate_limits(tmp_path):
    engines = [database.create_database_engine(tmp_path / 'shared.db') for _ in range(2)]
    database.create_schema(engines[0])
    def consume(index):
        try:
            with Session(engines[index % 2]) as session, session.begin():
                limits.consume(session, 'same-client', 'test', 3, 60, now=120)
            return True
        except HTTPException as e:
            assert e.status_code == 429
            return False
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert sum(pool.map(consume, range(10))) == 3
        with Session(engines[0]) as session, session.begin():
            limits.consume(session, 'same-client', 'test', 3, 60, now=180)
    finally:
        for engine in engines: engine.dispose()


def test_profile_quota_is_atomic_and_updates_remain_possible(tmp_path):
    engine = database.create_database_engine(tmp_path / 'quota.db')
    database.create_schema(engine)
    with Session(engine) as session, session.begin():
        uid = database.create_user(session).id
        database.register_movies(session, [1, 2])
    def write(movie):
        try:
            with Session(engine) as session, session.begin():
                database.enforce_rating_quota(session, uid, movie, 1)
                database.save_rating(session, uid, movie, 4)
            return True
        except HTTPException:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(write, [1, 2])) == 1
    with Session(engine) as session, session.begin():
        movie = next(iter(database.get_user_profile(session, uid)))
        database.enforce_rating_quota(session, uid, movie, 1)
        database.save_rating(session, uid, movie, 3.25)
    engine.dispose()


def test_body_limits_search_limits_and_creation_limits(api_paths):
    with TestClient(create_app(*api_paths)) as client:
        assert client.post('/users', content=b'x' * (limits.MAX_BODY_BYTES + 1)).status_code == 413
        assert client.get('/movies/search', params={'q': 'x' * 121}).status_code == 422
        assert client.get('/recommendations/popular?min_rating_count=999999999999').status_code == 422
        for _ in range(10): assert client.post('/users').status_code == 201
        denied = client.post('/users')
        assert denied.status_code == 429 and int(denied.headers['retry-after']) > 0
        assert client.get('/health').status_code == 200


def test_cooperative_computation_budget_stops_without_changing_default_math():
    from app.recommender import nearest_neighbors
    with budget.computation(-1):
        with pytest.raises(budget.WorkloadTimeout): budget.check()
    budget.check()


def test_profile_lifetime_capacity_preserves_existing_users(api_paths, monkeypatch):
    monkeypatch.setattr(limits, 'MAX_PROFILES', 2)
    with TestClient(create_app(*api_paths)) as client:
        first = client.post('/users').json()
        assert client.post('/users').status_code == 201
        assert client.post('/users').status_code == 503
        assert client.get(f"/users/{first['id']}", headers={'Authorization': 'Bearer ' + first['token']}).status_code == 200


def test_rate_window_cannot_rewind_or_refund_exhausted_capacity(tmp_path):
    engine = database.create_database_engine(tmp_path / 'clock.db')
    database.create_schema(engine)
    try:
        with Session(engine) as session, session.begin():
            limits.consume(session, 'client', 'clock', 1, 60, now=120)
        for now in (60, 120, 179):
            with pytest.raises(HTTPException) as error:
                with Session(engine) as session, session.begin():
                    limits.consume(session, 'client', 'clock', 1, 60, now=now)
            assert error.value.status_code == 429
        with Session(engine) as session, session.begin():
            limits.consume(session, 'client', 'clock', 1, 60, now=180)
    finally:
        engine.dispose()


def test_group_union_and_legacy_profile_limits_precede_computation(api_paths, monkeypatch):
    from app import recommender
    with TestClient(create_app(*api_paths)) as client:
        a, b = client.post('/users').json(), client.post('/users').json()
        auth = {'Authorization': 'Bearer ' + a['token']}
        grant = client.post(f"/users/{b['id']}/group-invitation", headers={'Authorization': 'Bearer ' + b['token']}).json()['code'].split(':')[1]
        with Session(client.app.state.engine) as session, session.begin():
            database.register_movies(session, [1, 2, 3])
            for movie in (1, 2): database.save_rating(session, a['id'], movie, 4)
            database.save_rating(session, b['id'], 3, 4)
        monkeypatch.setattr(recommender, 'recommend_details', lambda *args, **kwargs: pytest.fail('Oversized computation started'))
        monkeypatch.setattr(limits, 'MAX_PROFILE_RATINGS', 1)
        assert client.get(f"/users/{a['id']}/recommendations", headers=auth).status_code == 422
        monkeypatch.setattr(limits, 'MAX_PROFILE_RATINGS', 100)
        monkeypatch.setattr(limits, 'MAX_GROUP_RATINGS', 2)
        response = client.post('/recommendations/group', headers=auth, json={'user_ids': [a['id'], b['id']], 'invitations': {str(b['id']): grant}})
        assert response.status_code == 422


def test_actual_prepared_computation_deadline_releases_gate_and_connections(api_paths, monkeypatch):
    with TestClient(create_app(*api_paths)) as client:
        owner = client.post('/users').json()
        auth = {'Authorization': 'Bearer ' + owner['token']}
        with Session(client.app.state.engine) as session, session.begin():
            database.save_rating(session, owner['id'], 1, 1)
            database.save_rating(session, owner['id'], 2, 5)
        original = budget.computation
        monkeypatch.setattr(budget, 'computation', lambda: original(-1))
        response = client.get(f"/users/{owner['id']}/recommendations", headers=auth)
        assert response.status_code == 503
        assert 'time budget' in response.json()['detail']
        assert 'retry-after' not in response.headers  # Deadline failures are not capacity retries.
        assert client.app.state.engine.pool.checkedout() == 0
        monkeypatch.setattr(budget, 'computation', original)
        assert client.get(f"/users/{owner['id']}/recommendations", headers=auth).status_code == 200
