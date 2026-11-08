"""Credential-bearing invalid input is never a public diagnostic or log entry."""

import json
import logging
import os
import socket
import subprocess
import sys
import time
from http.client import HTTPConnection

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import create_app
from app.validation import public_validation_errors
from test_api import api_paths


def no_secrets(text, values):
    # A failing regression must not print even its disposable credential.
    if any(value in text for value in values):
        pytest.fail("Confidential input was included in diagnostics", pytrace=False)


@pytest.fixture
def private_client(api_paths):
    with TestClient(create_app(*api_paths)) as client:
        profile = client.post('/users').json()
        auth = {'Authorization': 'Bearer ' + profile['token']}
        yield client, profile, auth


@pytest.mark.parametrize('kind', [
    'authorization', 'nested_rating', 'invitation_value', 'invitation_key',
    'artwork_item', 'lookup_item', 'malformed_json', 'query', 'path',
])
def test_all_validation_sources_redact_input_and_sensitive_locations(private_client, caplog, kind):
    client, profile, auth = private_client
    secret = profile['token']
    recovery = f"{profile['id']}:{secret}"
    rating = f"/users/{profile['id']}/ratings/1"
    nested = {'password': secret, 'recovery_code': recovery,
              'credentials': [{'token': secret, 'access_token': secret}]}
    caplog.set_level(logging.DEBUG)
    if kind == 'authorization':
        response = client.get('/users/me', headers={'Authorization': 'Bearer ' + secret + ' ' * 60})
    elif kind == 'nested_rating':
        response = client.put(rating, headers=auth, json={'rating': nested})
    elif kind in {'invitation_key', 'invitation_value'}:
        grants = {secret: 'x' * 43} if kind == 'invitation_key' else {'999': nested}
        response = client.post('/recommendations/group', headers=auth,
                              json={'user_ids': [profile['id'], 999], 'invitations': grants})
    elif kind == 'artwork_item':
        response = client.post('/movies/artwork', json={'movie_ids': [nested]})
    elif kind == 'lookup_item':
        response = client.post(f"/users/{profile['id']}/ratings/lookup", headers=auth,
                               json={'movie_ids': [nested]})
    elif kind == 'malformed_json':
        response = client.put(rating, headers={**auth, 'Content-Type': 'application/json'},
                              content='{"rating": 4, "password": "' + secret + '\n"}')
    elif kind == 'query':
        response = client.get('/movies/search', params={'q': secret * 4})
    else:
        response = client.get('/users/' + secret, headers=auth)
    assert response.status_code == 422
    no_secrets(response.text, [secret, recovery])
    details = response.json()['detail']
    assert details and all(set(item) == {'loc', 'type', 'msg'} for item in details)
    assert all(item['loc'] and item['msg'] for item in details)
    # HTTPX's client-side request log includes the URL supplied by this test;
    # check application/server diagnostics separately. Production access logs
    # are disabled and covered by the real Uvicorn integration below.
    records = '\n'.join(record.getMessage() for record in caplog.records
                        if not record.name.startswith(('httpx', 'httpcore')))
    no_secrets(records, [secret, recovery])


def test_projection_rejects_custom_messages_context_types_and_dynamic_keys():
    secret = 'confidential-test-sentinel'
    details = public_validation_errors([
        {'type': 'value_error', 'msg': 'Rejected ' + secret,
         'loc': ('body', 'invitations', secret, '[key]'),
         'input': {'password': secret, 'nested': [secret]},
         'ctx': {'error': ValueError(secret)}, 'url': 'https://invalid.example/' + secret},
        {'type': secret, 'msg': secret, 'loc': ('body', secret), 'input': secret},
    ])
    no_secrets(json.dumps(details), [secret])
    assert details == [
        {'type': 'value_error', 'loc': ['body', 'invitations', 'member', 'field'], 'msg': 'Invalid value.'},
        {'type': 'value_error', 'loc': ['body', 'field'], 'msg': 'Invalid value.'},
    ]


def test_errors_preserve_actionable_field_and_numeric_type():
    assert public_validation_errors([
        {'type': 'finite_number', 'loc': ('body', 'rating'), 'input': float('nan')},
        {'type': 'int_type', 'loc': ('body', 'movie_ids', 2), 'input': {'token': 'ignored'}},
    ]) == [
        {'type': 'finite_number', 'loc': ['body', 'rating'], 'msg': 'Enter a finite number.'},
        {'type': 'int_type', 'loc': ['body', 'movie_ids', 2], 'msg': 'Enter a whole number.'},
    ]


def test_database_exception_response_and_handler_logs_remain_sanitized(private_client, monkeypatch, caplog):
    from app import database
    client, profile, auth = private_client
    secret = profile['token']
    def rejected(*args, **kwargs):
        raise OperationalError('private SQL ' + secret, {}, Exception(secret))
    monkeypatch.setattr(database, 'save_rating', rejected)
    caplog.set_level(logging.DEBUG)
    response = client.put(f"/users/{profile['id']}/ratings/1", headers=auth, json={'rating': 4})
    assert response.status_code == 500
    assert response.json() == {'detail': 'Database operation failed'}
    no_secrets(response.text + caplog.text, [secret])


def test_real_runtime_does_not_log_credentials_pasted_into_urls_or_headers(api_paths):
    prepared, database = api_paths
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    environment = {
        **os.environ, 'APP_ENV': 'development', 'PORT': str(port),
        'DATABASE_URL': 'sqlite:///' + str(database),
        'MOVIELENS_PREPARED_DIR': str(prepared), 'CORS_ALLOWED_ORIGINS': '',
        'TRUSTED_PROXY_IPS': '', 'TRAKT_CLIENT_ID': '', 'FANART_API_KEY': '',
        'MOVELLE_ARTWORK_CACHE_DIR': '', 'MOVELLE_ARTWORK_LINKS': '',
    }
    # Administrator-prepared fixtures omit opt-in archive provenance settings.
    environment.pop('MOVIELENS_ARCHIVE_URL', None)
    environment.pop('MOVIELENS_ARCHIVE_SHA256', None)
    # Exercise the real runtime, overriding only its listener to stay loopback.
    command = ("from app import runtime; launch = runtime.uvicorn.run; "
               "runtime.uvicorn.run = lambda app, **kw: "
               "launch(app, **{**kw, 'host': '127.0.0.1'}); runtime.main()")
    worker = subprocess.Popen([sys.executable, '-c', command], env=environment,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    def request(method, path, **options):
        connection = HTTPConnection('127.0.0.1', port, timeout=2)
        try:
            connection.request(method, path, **options)
            response = connection.getresponse()
            return response.status, response.read().decode()
        finally:
            connection.close()
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                if request('GET', '/health')[0] == 200:
                    break
            except OSError:
                pass
            if worker.poll() is not None or time.monotonic() >= deadline:
                pytest.fail('Isolated runtime did not become healthy', pytrace=False)
            time.sleep(0.1)
        status, body = request('POST', '/users')
        assert status == 201
        token = json.loads(body)['token']
        status, body = request('GET', '/movies/search?q=' + token * 4)
        assert status == 422
        no_secrets(body, [token])
        status, body = request('GET', '/users/me',
                               headers={'Authorization': 'Bearer ' + token + 'Z' * 60})
        assert status == 422
        no_secrets(body, [token])
    finally:
        if worker.poll() is None:
            worker.terminate()  # Only the process created by this test.
        try:
            stdout, stderr = worker.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            worker.kill()
            stdout, stderr = worker.communicate(timeout=5)
    no_secrets((stdout + stderr).decode(errors='replace'), [token])
