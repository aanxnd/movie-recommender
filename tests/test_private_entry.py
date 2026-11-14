"""Actual private composition on isolated SQLite, local signatures/mocked provider."""
import json
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url

from app import database, private_entry, provisioning_principal, security, supabase_auth
from app.models import Credential, User
from test_api import api_paths
from test_private_boundary import private_inputs
from test_supabase_claims import evidence
from test_supabase_policy import account


@pytest.fixture
def private_app(private_inputs, api_paths, tmp_path, monkeypatch, account):
    env, targets = private_inputs
    env['MOVELLE_PRIVATE_PREPARED_DIR'] = str(api_paths[0])
    path = tmp_path / 'targets.json'; path.write_text(json.dumps(targets))
    env['MOVELLE_PRIVATE_TARGETS_FILE'] = str(path)
    for key, value in env.items(): monkeypatch.setenv(key, value)
    e, policy, user, calls = account
    engine = database.create_database_engine(api_paths[1]); database.create_schema(engine)
    monkeypatch.setattr(database, 'create_schema', lambda *_: pytest.fail('Startup migration'))
    def isolated_engine(*args, **kwargs):
        assert make_url(kwargs['database_url']) == make_url(env['MOVELLE_PRIVATE_DATABASE_URL'])
        return engine
    monkeypatch.setattr(database, 'create_database_engine', isolated_engine)
    monkeypatch.setattr(supabase_auth, 'SupabaseAccessPolicy', lambda **_: policy)
    monkeypatch.setattr(provisioning_principal, 'SupabaseAccessPolicy', lambda **_: policy)
    monkeypatch.setattr(security, 'authenticate', lambda *_: pytest.fail('Legacy fallback'))
    with TestClient(private_entry.application(), base_url=targets['backend_origin']) as client:
        h = {'Origin': targets['frontend_origin'], 'x-movelle-private-gate': env['MOVELLE_PRIVATE_GATE_SECRET']}
        yield client, h, e, user, calls, engine


def test_private_authentication_profile_ownership_mfa_and_no_legacy(private_app):
    c, h, e, user, calls, engine = private_app
    assert c.get('/health').status_code == 403 and not calls
    assert c.get('/health', headers=h).status_code == 200
    assert c.get('/movies/search?q=Film', headers=h).status_code == 200
    for path in ['/users', '/users/restore', '/docs', '/openapi.json']:
        assert c.post(path, headers=h).status_code in {404, 405}
    for token in ['legacy-opaque', e.sign({'iss': 'https://evil.invalid'}), 'invalid']:
        assert c.get('/users/me', headers={**h, 'Authorization': 'Bearer ' + token}).status_code == 401
    def auth(): return {**h, 'Authorization': 'Bearer ' + e.sign()}
    del user['factors']  # Real reviewed zero-factor provider serialization.
    assert c.post('/auth/profile', headers=auth(), json={'username': 'PrivateAlice'}).status_code == 200
    uid = c.get('/users/me', headers=auth()).json()['id']
    with Session(engine) as s, s.begin():
        other = database.create_user(s).id
    assert c.put(f'/users/{uid}/ratings/1', headers=auth(), json={'rating': 4.5}).status_code == 200
    assert c.get(f'/users/{other}', headers=auth()).status_code == 404
    assert c.put(f'/users/{other}/ratings/1', headers=auth(), json={'rating': 4}).status_code == 404
    assert c.post('/recommendations/group', headers=auth(), json={'user_ids': [uid, other]}).status_code == 404
    user['email_confirmed_at'] = None
    assert c.get('/users/me', headers=auth()).status_code == 401
    user['email_confirmed_at'] = '2026-01-01T00:00:00Z'
    user['factors'] = [dict(id=str(uuid4()), factor_type='totp', status='verified')]
    assert c.get('/users/me', headers=auth()).status_code == 401
    assert c.get('/users/me', headers={**h, 'Authorization': 'Bearer ' + e.sign({'aal': 'aal2'})}).json()['id'] == uid
    with Session(engine) as s:
        assert len(s.query(User).all()) == 2 and s.query(Credential).count() == 0


def test_private_request_limits_origin_and_provider_outage(private_app, monkeypatch):
    c, h, e, user, calls, _ = private_app
    auth = {**h, 'Authorization': 'Bearer ' + e.sign()}
    assert c.post('/auth/profile', headers=auth, content=b'x' * 16385).status_code == 413
    assert c.get('/health', headers={**h, 'Origin': 'https://evil.invalid'}).status_code == 403
    assert not calls
    monkeypatch.setattr('app.supabase_policy._read_user', lambda *_: (_ for _ in ()).throw(TimeoutError('sensitive')))
    result = c.get('/auth/profile', headers=auth)
    assert result.status_code == 503 and 'sensitive' not in result.text


def test_missing_private_config_never_starts(monkeypatch):
    monkeypatch.delenv('MOVELLE_PRIVATE_MODE', raising=False)
    with pytest.raises(RuntimeError, match='^Private application configuration unavailable$'):
        private_entry.application()
