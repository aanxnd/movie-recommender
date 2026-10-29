from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app import bootstrap, database, readiness, recommender
from app.main import create_app
from test_api import api_paths
from test_bootstrap import release, mock_download


def test_ready_callers_share_probe_and_cached_results(monkeypatch):
    entered, finish = Event(), Event()
    calls = []
    def probe(engine):
        calls.append(1)
        entered.set()
        assert finish.wait(3)
        return True
    monkeypatch.setattr(readiness, 'database_ready', probe)
    monitor = readiness.CachedReadiness(object())
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(monitor.check)
        assert entered.wait(3)
        second = pool.submit(monitor.check)
        finish.set()
        assert first.result() and second.result()
    assert monitor.check() is True and len(calls) == 1
    monitor.checked_at = 0
    monkeypatch.setattr(readiness, 'database_ready', lambda engine: False)
    assert monitor.check() is False


def test_no_database_connection_is_held_during_personal_or_group_compute(api_paths, monkeypatch):
    with TestClient(create_app(*api_paths)) as client:
        a, b = client.post('/users').json(), client.post('/users').json()
        auth = {'Authorization': 'Bearer ' + a['token']}
        grant = client.post(f"/users/{b['id']}/group-invitation", headers={'Authorization': 'Bearer ' + b['token']}).json()['code'].split(':')[1]
        original = recommender.recommend_details
        calls = []
        def compute(*args, **kwargs):
            assert client.app.state.engine.pool.checkedout() == 0
            calls.append(1)
            return original(*args, **kwargs)
        monkeypatch.setattr(recommender, 'recommend_details', compute)
        assert client.get(f"/users/{a['id']}/recommendations", headers=auth).status_code == 200
        assert client.post('/recommendations/group', headers=auth, json={'user_ids': [a['id'], b['id']], 'invitations': {str(b['id']): grant}}).status_code == 200
        assert len(calls) == 2


def test_changed_pin_does_not_relabel_existing_data(release, tmp_path, monkeypatch):
    _, content, digest = release
    mock_download(monkeypatch, content)
    target = tmp_path / 'runtime/ml-32m-v1'
    bootstrap.ensure_prepared(target, bootstrap.RELEASE_URL, digest)
    before = bootstrap.marker_path(target).read_bytes()
    with pytest.raises(bootstrap.BootstrapError, match='fresh versioned'):
        bootstrap.ensure_prepared(target, bootstrap.RELEASE_URL, 'f' * 64)
    assert bootstrap.marker_path(target).read_bytes() == before


def test_direct_asgi_rejects_same_shape_corruption(api_paths):
    target, path = api_paths
    file = target / 'profile_ratings.npy'
    content = bytearray(file.read_bytes())
    content[-1] ^= 1
    file.write_bytes(content)
    with pytest.raises(RuntimeError, match='checksum'):
        with TestClient(create_app(target, path)): pass
    assert not path.exists()


def test_concurrent_schema_initializers_are_serialized(tmp_path):
    engines = [database.create_database_engine(tmp_path / 'init.db') for _ in range(2)]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(database.create_schema, engines))
    finally:
        for engine in engines: engine.dispose()


def test_current_version_does_not_hide_missing_schema_columns(tmp_path):
    from app.migrations import check_schema
    engine = database.create_database_engine(tmp_path / 'incomplete.db')
    try:
        database.create_schema(engine)
        check_schema(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql('ALTER TABLE profile_credentials DROP COLUMN expires_at')
        with pytest.raises(ValueError, match='incomplete'):
            check_schema(engine)
    finally:
        engine.dispose()
