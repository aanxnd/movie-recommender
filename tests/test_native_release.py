"""No hosted resources: explicit target validation and synthetic native composition."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app import native_release as release
from test_staging_app import staging, headers, create
from test_staging_app import pg_engine, api_paths, account, evidence


def config():
    targets = dict(approved=True, frontend_origin='https://frontend.example',
        supabase_url='https://' + 'a' * 20 + '.supabase.co', database_host='ep-fixture.ca.neon.tech', database_name='movelle')
    env = dict(APP_ENV='production', MOVELLE_NATIVE_MODE='native-release', CORS_ALLOWED_ORIGINS=targets['frontend_origin'],
        MOVELLE_NATIVE_PUBLISHABLE_KEY='sb_publishable_offline', MOVELLE_NATIVE_PREPARED_DIR='/prepared',
        MOVELLE_NATIVE_DATABASE_URL='postgresql://movelle_native:synthetic@ep-fixture.ca.neon.tech/movelle'
            '?sslmode=verify-full&sslrootcert=system&channel_binding=require')
    return env, targets


@pytest.mark.parametrize('field,value', [('APP_ENV', 'development'), ('MOVELLE_NATIVE_MODE', ''),
    ('CORS_ALLOWED_ORIGINS', '*'), ('TRUSTED_PROXY_IPS', '*'), ('PGHOST', 'foreign.invalid'),
    ('MOVELLE_NATIVE_PUBLISHABLE_KEY', 'service_role'), ('MOVELLE_NATIVE_PREPARED_DIR', ''),
    ('MOVELLE_NATIVE_DATABASE_URL', 'sqlite:///production.db'),
    ('MOVELLE_NATIVE_DATABASE_URL', 'postgresql://postgres:synthetic@foreign.invalid/movelle')])
def test_ambient_or_mismatched_config_denied(field, value):
    env, targets = config()
    env[field] = value
    with pytest.raises(ValueError, match='Approved native'):
        release.settings(env, targets)


@pytest.mark.parametrize('origin', ['http://frontend.example', 'https://frontend.example/',
    'https://frontend.example?token=private', 'https://user:private@frontend.example', 'https://*.example'])
def test_non_exact_origins_denied(origin):
    env, targets = config()
    targets['frontend_origin'] = env['CORS_ALLOWED_ORIGINS'] = origin
    with pytest.raises(ValueError):
        release.settings(env, targets)


def test_target_file_requires_explicit_review_and_unique_bounded_json(tmp_path):
    env, targets = config()
    file = tmp_path / 'targets.json'
    env['MOVELLE_NATIVE_TARGETS_FILE'] = str(file)
    file.write_text(json.dumps(targets))
    assert release.load_settings(env)['project_url'] == targets['supabase_url']
    for raw in ['{}', '{"approved":false,"approved":true}', ' ' * 8193]:
        file.write_text(raw)
        with pytest.raises(ValueError):
            release.load_settings(env)


def test_native_release_reuses_verified_routes_without_legacy_or_private_gate(staging, monkeypatch):
    client, e, _, engine = staging
    # Inject only trusted local fixture configuration; environment validation is tested above.
    monkeypatch.setattr(release, 'load_settings', lambda _: dict(prepared_dir='/injected-unused',
        database_url=engine.url.render_as_string(hide_password=False), project_url='https://' + 'a' * 20 + '.supabase.co',
        publishable_key='sb_publishable_offline', audience='authenticated', origin='http://127.0.0.1:5173'))
    # Reuse the already loaded fixture lifespan without touching any hosted target.
    monkeypatch.setattr(release, 'compose_native_app', lambda **_: client.app)
    app = release.application()
    assert all(getattr(r, 'path', '') not in {'/docs', '/openapi.json', '/users'} for r in app.routes)
    uid = create(client, e)
    assert client.get('/auth/settings', headers=headers(e)).json()['revision'] == '1'
    assert client.patch('/auth/settings', headers=headers(e), json={'username': 'Renamed', 'revision': '1'}).status_code == 200
    assert client.get('/movies/search?q=Film').status_code == 200
    assert client.get('/users/me', headers={'Authorization': 'Bearer legacy'}).status_code == 401
    assert client.put(f'/users/{uid}/ratings/1', headers=headers(e), json={'rating': 4}).status_code == 200
    preflight = client.options('/auth/settings', headers={'Origin': 'http://127.0.0.1:5173',
        'Access-Control-Request-Method': 'PATCH', 'Access-Control-Request-Headers': 'Authorization,Content-Type'})
    assert preflight.status_code == 200


def test_defaults_still_select_legacy_not_native():
    assert 'app.runtime' in Path('Dockerfile').read_text()
    assert 'app.native_release' not in Path('app/runtime.py').read_text()
