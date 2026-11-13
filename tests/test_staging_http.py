"""Real loopback HTTP + actual staging app/PostgreSQL; fictional Auth HTTP is explicit."""
import os
import socket

import httpx
import pytest

from staging_fixture_server import staging_fixture
from test_postgresql_concurrency import pg_engine


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); return sock.getsockname()[1]


def test_real_http_native_staging_roundtrip_and_shutdown(pg_engine):
    # pg_engine validates disposable loopback configuration; fixture owns a different random schema.
    with staging_fixture(os.environ['POSTGRES_TEST_URL'], api_port=free_port(), provider_port=free_port()) as (api, auth, _):
        with httpx.Client(timeout=10, trust_env=False) as client:
            assert client.get(api+'/ready').json() == {'status': 'ok'}
            assert client.get(api+'/movies/search?q=Film').status_code == 200
            assert client.get(auth+'/_fixture/state').json()['users'] == 0
            token = client.post(auth+'/auth/v1/token?grant_type=password', json={
                'email': 'alice@example.invalid', 'password': 'fixture-password'}).json()['access_token']
            bearer = {'Authorization': 'Bearer '+token}
            assert client.post(api+'/auth/profile', headers=bearer, json={'username': 'MovieFan'}).status_code == 401
            user = client.get(auth+'/auth/v1/user', headers=bearer).json()
            path = auth+'/auth/v1/factors/'+user['factors'][0]['id']
            challenge = client.post(path+'/challenge', headers=bearer, json={}).json()['id']
            code = client.get(auth+'/_fixture/otp').json()['code']
            promoted = client.post(path+'/verify', headers=bearer, json={'challenge_id': challenge, 'code': code}).json()
            bearer = {'Authorization': 'Bearer '+promoted['access_token']}
            assert client.post(api+'/auth/profile', headers=bearer, json={'username': 'MovieFan'}).status_code == 200
            uid = client.get(api+'/users/me', headers=bearer).json()['id']
            assert client.put(api+f'/users/{uid}/ratings/1', headers=bearer, json={'rating': 4}).status_code == 200
            assert client.get(api+f'/users/{uid}/ratings/details', headers=bearer).json()['total'] == 1
            assert client.get(auth+'/_fixture/state').json() == {'users': 1, 'identities': 1, 'ratings': 1, 'credentials': 0}
            assert client.post(api+'/users').status_code == 404
    with httpx.Client(timeout=.3, trust_env=False) as client, pytest.raises((httpx.ConnectError, httpx.ConnectTimeout)):
        client.get(api+'/health')
