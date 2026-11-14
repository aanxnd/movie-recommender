"""Offline only: synthetic targets/keys; no database/provider connections."""
import json
from dataclasses import asdict

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.private_config import PROJECT, PRODUCTION_API, PRODUCTION_BRANCH, load_settings, settings
from app.private_gate import PrivateGate


@pytest.fixture
def private_inputs():
    frontend, backend = 'https://owner-preview.vercel.app', 'https://private.example.azurecontainerapps.io'
    host = 'ep-private-test.canadacentral.azure.neon.tech'
    env = dict(APP_ENV='production', MOVELLE_PRIVATE_MODE='private-stage23', CORS_ALLOWED_ORIGINS=frontend,
        MOVELLE_PRIVATE_GATE_SECRET='s' * 43, MOVELLE_PRIVATE_PUBLISHABLE_KEY='sb_publishable_offline',
        MOVELLE_PRIVATE_PREPARED_DIR='offline-prepared', MOVELLE_PRIVATE_DATABASE_URL=
        f'postgresql://movelle_private_stage23:synthetic@{host}/movelle_private_stage23'
        '?sslmode=verify-full&sslrootcert=system&channel_binding=require')
    targets = dict(approved=True, branch_name='private-stage23', branch_id='br-private-test',
        azure_app='movie-recommender-api-private', supabase_url=PROJECT, frontend_origin=frontend,
        backend_origin=backend, database_host=host, protected_database_hosts=['ep-production.neon.tech'])
    return env, targets


def test_pinned_settings_have_no_secret_repr_or_ambient_fallback(private_inputs):
    env, targets = private_inputs
    env['DATABASE_URL'] = 'must-not-be-used'
    result = settings(env, targets)
    assert 'synthetic' not in repr(result) and 's' * 43 not in repr(result)
    assert 'must-not-be-used' not in str(asdict(result))
    assert result.frontend == targets['frontend_origin']


@pytest.mark.parametrize('key,value', [('approved', False), ('branch_name', 'production'),
    ('branch_id', PRODUCTION_BRANCH), ('azure_app', 'movie-recommender-api'), ('supabase_url', 'https://other.supabase.co'),
    ('frontend_origin', 'https://owner-preview.vercel.app/'), ('frontend_origin', 'https://evil.invalid'),
    ('backend_origin', PRODUCTION_API), ('backend_origin', 'https://user:secret@private.azurecontainerapps.io'),
    ('backend_origin', 'http://private.azurecontainerapps.io'), ('backend_origin', 'https://private.azurecontainerapps.io:443'),
    ('database_host', 'ep-production.neon.tech'), ('protected_database_hosts', []), ('branch_id', None),
    ('protected_database_hosts', ['EP-PRIVATE-TEST.CANADACENTRAL.AZURE.NEON.TECH'])])
def test_unapproved_or_production_targets_deny(private_inputs, key, value):
    env, targets = private_inputs
    targets[key] = value
    with pytest.raises(ValueError, match='^Approved isolated private configuration required$'):
        settings(env, targets)


@pytest.mark.parametrize('key,value', [('APP_ENV', 'development'), ('MOVELLE_PRIVATE_MODE', 'production'),
    ('CORS_ALLOWED_ORIGINS', '*'), ('TRUSTED_PROXY_IPS', '*'), ('PGHOST', 'production'),
    ('MOVELLE_PRIVATE_GATE_SECRET', 'weak'), ('MOVELLE_PRIVATE_PUBLISHABLE_KEY', 'service_role'),
    ('MOVELLE_PRIVATE_DATABASE_URL', 'postgresql://x:y@127.0.0.1/production')])
def test_bad_environment_does_not_leak_values(private_inputs, key, value):
    env, targets = private_inputs; env[key] = value
    with pytest.raises(ValueError, match='^Approved isolated private configuration required$'):
        settings(env, targets)


@pytest.mark.parametrize('old,new', [('verify-full', 'require'), ('sslrootcert=system', 'host=evil.invalid'),
    ('channel_binding=require', 'options=-c%20search_path=public'), ('movelle_private_stage23:', 'neondb_owner:'),
    ('/movelle_private_stage23?', '/neondb?'), ('ep-private-test', 'ep-different')])
def test_database_target_and_tls_are_exact(private_inputs, old, new):
    env, targets = private_inputs; env['MOVELLE_PRIVATE_DATABASE_URL'] = env['MOVELLE_PRIVATE_DATABASE_URL'].replace(old, new)
    with pytest.raises(ValueError): settings(env, targets)


def test_manifest_size_duplicates_and_missing_inputs_fail_closed(tmp_path, private_inputs):
    env, targets = private_inputs; path = tmp_path / 'targets.json'
    env['MOVELLE_PRIVATE_TARGETS_FILE'] = str(path)
    for raw in ['{"approved":true,"approved":false}', ' ' * 8193, 'not-json']:
        path.write_text(raw)
        with pytest.raises(ValueError): load_settings(env)
    path.write_text(json.dumps(targets))
    assert load_settings(env) == settings(env, targets)
    del env['MOVELLE_PRIVATE_GATE_SECRET']
    with pytest.raises(ValueError): load_settings(env)


def test_gate_runs_before_application_and_strips_capability(private_inputs):
    env, targets = private_inputs; s = settings(env, targets); app = FastAPI(); calls = []
    @app.post('/check')
    async def check(request: Request):
        calls.append(request)
        return {'headers': dict(request.headers), 'client': request.client.host}
    app.add_middleware(PrivateGate, secret=s.gate, frontend=s.frontend, backend=s.backend)
    valid = [('host', s.backend[8:]), ('origin', s.frontend), ('x-movelle-private-gate', s.gate)]
    with TestClient(app) as client:
        for headers in [[], valid[:2], valid + [valid[-1]], valid + [valid[1]],
                [(k, 'wrong' if k == 'x-movelle-private-gate' else v) for k, v in valid],
                [(k, 'evil.invalid' if k == 'host' else v) for k, v in valid]]:
            r = client.post('/check', headers=headers, content=b'x' * 20000)
            assert r.status_code == 403 and r.headers['cache-control'] == 'no-store'
            assert s.gate not in r.text and not calls
        r = client.post('/check', headers=valid + [('x-forwarded-for', 'evil'), ('forwarded', 'evil')])
        assert r.status_code == 200 and len(calls) == 1
        assert not any(k in r.json()['headers'] for k in ['x-movelle-private-gate', 'x-forwarded-for', 'forwarded'])
        assert r.json()['client'] == 'testclient'
