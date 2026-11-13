"""The fixture is a simulator, not a hosted Supabase acceptance test."""
import base64
import hashlib
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from staging_provider import ProviderFixture


def test_fictional_provider_enforces_its_pkce_binding_and_single_use():
    p = ProviderFixture(); verifier = 'fixture-code-verifier'
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    with TestClient(p.app) as client:
        response = client.post('/auth/v1/signup', json={'email': 'new@example.invalid', 'password': 'fixture', 'code_challenge': challenge})
        uid = response.json()['id']; code = next(reversed(p.links))
        p.users[uid]['email_confirmed_at'] = '2026-01-01T00:00:00Z'  # Simulated mailbox completion, no email.
        assert client.post('/auth/v1/token?grant_type=password', json={'email': 'new@example.invalid', 'password': 'wrong'}).status_code == 400
        body = {'auth_code': code, 'code_verifier': verifier}
        result = client.post('/auth/v1/token?grant_type=pkce', json=body)
        assert result.status_code == 200 and result.json()['user']['id'] == uid
        assert client.post('/auth/v1/token?grant_type=pkce', json=body).status_code == 422


def test_simulated_mfa_and_recovery_do_not_substitute_for_each_other():
    p = ProviderFixture(); uid = next(iter(p.users)); token = p.token(uid, method='recovery')
    auth = {'Authorization': 'Bearer ' + token['access_token']}
    factor = p.users[uid]['factors'][0]['id']
    with TestClient(p.app) as client:
        assert client.put('/auth/v1/user', headers=auth, json={'password': 'new'}).status_code == 401
        challenge = client.post('/auth/v1/factors/'+factor+'/challenge', headers=auth, json={}).json()['id']
        result = client.post('/auth/v1/factors/'+factor+'/verify', headers=auth, json={'challenge_id': challenge, 'code': p.otp()})
        assert result.status_code == 200
        assert client.put('/auth/v1/user', headers={'Authorization': 'Bearer '+result.json()['access_token']}, json={'password': 'new'}).status_code == 200
        assert all(len(event) == 2 for event in p.events)


def test_synthetic_otp_survives_clock_rollover_but_challenges_still_expire_and_reject_replay():
    p = ProviderFixture(); uid = next(iter(p.users)); token = p.token(uid)
    auth = {'Authorization': 'Bearer ' + token['access_token']}
    path = '/auth/v1/factors/' + p.users[uid]['factors'][0]['id']
    with TestClient(p.app) as client:
        challenge = client.post(path+'/challenge', headers=auth, json={}).json()['id']
        boundary = (int(time.time()) // 30) * 30 + 29.999
        with patch('staging_provider.time.time', return_value=boundary): code = p.otp()
        body = {'challenge_id': challenge, 'code': code}
        with patch('staging_provider.time.time', return_value=boundary+.002):
            assert p.otp() == code
            assert client.post(path+'/verify', headers=auth, json=body).status_code == 200
            assert client.post(path+'/verify', headers=auth, json=body).status_code == 400
        expired = client.post(path+'/challenge', headers=auth, json={}).json()['id']
        with patch('staging_provider.time.time', return_value=p.challenges[expired][2]+1):
            assert client.post(path+'/verify', headers=auth,
                               json={'challenge_id': expired, 'code': p.otp()}).status_code == 400
