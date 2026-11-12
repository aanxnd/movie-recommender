"""Offline HTTP composition only; production app never mounts these routes."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app import limits, provisioning_principal, provisioning_routes
from app.models import RateBucket
from test_postgresql_concurrency import pg_engine
from test_user_identities import identity_engine
from test_provisioning import counts
from test_supabase_claims import evidence
from test_supabase_policy import account
from test_supabase_jwt import ORIGIN


@pytest.fixture
def setup_route(identity_engine, account, monkeypatch):
    e, policy, user, calls = account
    user['factors'] = [dict(id=str(uuid4()), factor_type='totp', status='verified')]
    monkeypatch.setattr(provisioning_principal, 'SupabaseAccessPolicy', lambda **_: policy)
    application = FastAPI()
    application.state.engine = identity_engine
    application.add_middleware(limits.RequestLimits)
    application.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5173'],
                               allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])
    router = provisioning_routes.make_provisioning_router(project_url=ORIGIN, audience='authenticated',
        publishable_key='sb_publishable_offline', session_factory=lambda: Session(identity_engine),
        allowed_origins=['http://127.0.0.1:5173'])
    application.include_router(router)
    with TestClient(application) as client:
        yield SimpleNamespace(client=client, evidence=e, user=user, calls=calls, engine=identity_engine,
                              headers={'Authorization': 'Bearer ' + e.sign({'aal': 'aal2'}),
                                       'Origin': 'http://127.0.0.1:5173'})


def test_subject_only_read_create_and_retry(setup_route):
    s = setup_route
    assert s.client.get('/auth/profile', headers=s.headers).json() == {'status': 'eligible'}
    for name in ('Alice_01', 'ChangedName'):
        response = s.client.post('/auth/profile', headers=s.headers, json={'username': name})
        assert response.status_code == 200 and response.json() == {'status': 'complete', 'username': 'Alice_01'}
        assert response.headers['cache-control'] == 'no-store'
    assert s.client.get('/auth/profile', headers=s.headers).json() == response.json()
    assert counts(s.engine) == (1, 1, 0, 0, 0)


@pytest.mark.parametrize('body', [None, [], 'private', {}, {'username': None}, {'username': 'ADMIN'},
    {'username': 'Alice', 'user_id': 10}, {'username': 'Alice', 'subject': 'private'}, {'username': 'éabc'}])
def test_invalid_payload_redaction(setup_route, body):
    s = setup_route
    response = s.client.post('/auth/profile', headers=s.headers, json=body)
    assert response.status_code == 422 and response.json() == {'detail': 'Invalid profile input'}
    assert response.headers['cache-control'] == 'no-store'
    assert counts(s.engine) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize('origin', ['https://evil.invalid', 'null', 'http://127.0.0.1:5173.evil.invalid'])
def test_cross_origin_and_owner_query_denied(setup_route, origin):
    s = setup_route
    headers = {**s.headers, 'Origin': origin}
    assert s.client.post('/auth/profile', headers=headers, json={'username': 'Alice'}).status_code == 403
    assert s.client.get('/auth/profile?user_id=10', headers=s.headers).status_code == 422
    assert counts(s.engine) == (0, 0, 0, 0, 0)


def test_http_auth_and_empty_inventory_remain_closed(setup_route):
    s = setup_route
    for header in ({}, {'Authorization': 'Bearer ' + 'a' * 43}):
        assert s.client.post('/auth/profile', headers=header, json={'username': 'Alice'}).status_code == 401
    s.user['factors'] = []
    assert s.client.post('/auth/profile', headers=s.headers, json={'username': 'Alice'}).status_code == 401
    assert counts(s.engine) == (0, 0, 0, 0, 0)


def test_different_subject_cannot_claim_name_or_read_profile(setup_route):
    s = setup_route
    assert s.client.post('/auth/profile', headers=s.headers, json={'username': 'Alice'}).status_code == 200
    other = uuid4()
    s.user['id'] = str(other)  # Same confirmed email is deliberately not linking authority.
    headers = {**s.headers, 'Authorization': 'Bearer ' + s.evidence.sign({'sub': str(other), 'aal': 'aal2'})}
    assert s.client.get('/auth/profile', headers=headers).json() == {'status': 'eligible'}
    response = s.client.post('/auth/profile', headers=headers, json={'username': 'ALICE'})
    assert response.status_code == 409 and response.json() == {'detail': 'Username unavailable'}
    assert counts(s.engine) == (1, 1, 0, 0, 0)


def test_rate_admission_not_refunded_and_no_duplicate_creation(setup_route):
    s = setup_route
    for _ in range(10):
        assert s.client.post('/auth/profile', headers=s.headers, json={'username': 'Alice'}).status_code == 200
    response = s.client.post('/auth/profile', headers=s.headers, json={'username': 'Alice'})
    assert response.status_code == 429 and int(response.headers['retry-after']) > 0
    assert response.headers['cache-control'] == 'no-store'
    assert counts(s.engine) == (1, 1, 0, 0, 0)
    assert s.client.get('/auth/profile', headers=s.headers).json()['status'] == 'complete'


def test_provider_failure_cannot_fall_back(setup_route, monkeypatch):
    s = setup_route
    def failed(*_): raise TimeoutError('private diagnostics')
    monkeypatch.setattr('app.supabase_policy._read_user', failed)
    response = s.client.post('/auth/profile', headers=s.headers, json={'username': 'Alice'})
    assert response.status_code == 503 and 'private' not in response.text
    assert counts(s.engine) == (0, 0, 0, 0, 0)


def test_bounded_body_and_cors_preflight(setup_route):
    s = setup_route
    assert s.client.post('/auth/profile', headers=s.headers, content=b'x' * 16385).status_code == 413
    response = s.client.options('/auth/profile', headers={'Origin': s.headers['Origin'],
        'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'Authorization,Content-Type'})
    assert response.status_code == 200 and response.headers['access-control-allow-origin'] == s.headers['Origin']
    assert 'access-control-allow-credentials' not in response.headers


@pytest.mark.parametrize('origins', [[], ['*'], ['https://example.invalid/'], ['https://x:y@example.invalid'],
                                  ['http://localhost:5173'], ['https://example.invalid?x=1']])
def test_no_guessed_or_wildcard_origins(origins):
    with pytest.raises(ValueError):
        provisioning_routes.make_provisioning_router(project_url=ORIGIN, audience='authenticated',
            publishable_key='sb_publishable_offline', session_factory=lambda: None, allowed_origins=origins)
