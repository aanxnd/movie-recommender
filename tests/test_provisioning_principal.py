"""Real offline signatures; provisioning needs no mapping or database connection."""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import re
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app import provisioning_principal as principal
from app.supabase_policy import AccessDenied
from test_supabase_policy import account
from test_supabase_claims import evidence
from test_supabase_jwt import ORIGIN


@pytest.fixture
def provision_auth(account, monkeypatch):
    e, policy, user, calls = account
    user['factors'] = [dict(id=str(uuid4()), factor_type='totp', status='verified')]
    monkeypatch.setattr(principal, 'SupabaseAccessPolicy', lambda **_: policy)
    dependency = principal.make_provisioning_dependency(project_url=ORIGIN, audience='authenticated',
                                                        publishable_key='sb_publishable_offline')
    app = FastAPI()
    results = []
    @app.get('/probe')
    def probe(value=Depends(dependency)):
        results.append(value)
        return {'ok': True}
    with TestClient(app) as client:
        yield e, policy, user, calls, client, results


def test_verified_unlinked_subject_needs_no_database(provision_auth):
    e, _, _, calls, client, results = provision_auth
    token = e.sign({'aal': 'aal2'})
    response = client.get('/probe?user_id=123&sub=untrusted', headers={'Authorization': 'Bearer ' + token})
    assert response.json() == {'ok': True} and response.headers['cache-control'] == 'no-store'
    value = results[0]
    assert value.subject == e.subject and value.session_id == e.session_id and value.aal == 'aal2'
    assert not hasattr(value, 'user_id') and str(e.subject) not in repr(value)
    with pytest.raises(FrozenInstanceError): value.subject = uuid4()
    assert len(calls) == 1


@pytest.mark.parametrize('factors', [None, [], {}, [{'status': 'verified'}]])
def test_unknown_or_conflicting_inventory_never_qualifies(provision_auth, factors):
    e, _, user, _, client, results = provision_auth
    user['factors'] = factors
    response = client.get('/probe', headers={'Authorization': 'Bearer ' + e.sign({'aal': 'aal2'})})
    assert response.status_code in {401, 503} and not results


def test_provisioning_uses_the_same_zero_factor_policy(account):
    e, policy, user, _ = account
    assert policy.check(e.sign()).aal == 'aal1'
    assert policy.check_for_provisioning(e.sign()).subject == e.subject


@pytest.mark.parametrize('omitted', [False, True])
def test_native_zero_factor_subject_can_provision_without_mfa(provision_auth, omitted):
    e, _, user, _, client, results = provision_auth
    user['factors'] = []
    if omitted: del user['factors']
    assert client.get('/probe', headers={'Authorization': 'Bearer ' + e.sign()}).status_code == 200
    assert results[-1].subject == e.subject


@pytest.mark.parametrize('status,aal,code', [('verified', 'aal1', 401), ('verified', 'aal2', 200),
                                           ('unverified', 'aal1', 200)])
def test_provisioning_preserves_existing_factor_policy(provision_auth, status, aal, code):
    e, _, user, _, client, _ = provision_auth
    user['factors'][0]['status'] = status
    assert client.get('/probe', headers={'Authorization': 'Bearer ' + e.sign({'aal': aal})}).status_code == code


@pytest.mark.parametrize('changes,kwargs', [({'exp': 1}, {}), ({'iss': 'https://other.invalid'}, {}),
    ({'aud': 'other'}, {}), ({'is_anonymous': True}, {}), ({}, {'key': ec.generate_private_key(ec.SECP256R1())})])
def test_bad_signed_identity_cannot_provision(provision_auth, changes, kwargs):
    e, _, _, _, client, results = provision_auth
    assert client.get('/probe', headers={'Authorization': 'Bearer ' + e.sign(changes, **kwargs)}).status_code == 401
    assert not results


@pytest.mark.parametrize('field,value', [('email_confirmed_at', None), ('is_anonymous', True),
                                        ('id', str(uuid4())), ('email', None)])
def test_current_provider_identity_is_required(provision_auth, field, value):
    e, _, user, _, client, _ = provision_auth
    user[field] = value
    assert client.get('/probe', headers={'Authorization': 'Bearer ' + e.sign({'aal': 'aal2'})}).status_code == 401


@pytest.mark.parametrize('headers', [{}, {'Authorization': 'Bearer ' + 'a' * 43},
    [('Authorization', 'Bearer a.b.c'), ('authorization', 'Bearer a.b.c')]])
def test_no_legacy_or_ambiguous_bearer(provision_auth, headers):
    _, _, _, calls, client, _ = provision_auth
    assert client.get('/probe', headers=headers).status_code == 401 and not calls


def test_provider_failure_is_generic_and_no_stale_success(provision_auth, monkeypatch, caplog):
    e, _, user, _, client, _ = provision_auth
    token = e.sign({'aal': 'aal2'})
    assert client.get('/probe', headers={'Authorization': 'Bearer ' + token}).status_code == 200
    def failed(*_): raise TimeoutError('private diagnostics')
    monkeypatch.setattr('app.supabase_policy._read_user', failed)
    response = client.get('/probe', headers={'Authorization': 'Bearer ' + token})
    assert response.status_code == 503
    for secret in (token, str(e.subject), user['email'], 'private diagnostics'):
        assert secret not in response.text + caplog.text


@pytest.mark.parametrize('value', [None, '', ' aa', 'aa ', 'a' * 31, 'éabc', 'Ａlice', 'a-b', 'alice\n',
                                  'root', 'ADMIN', True, 123, [], {}])
def test_invalid_username(value):
    with pytest.raises(ValidationError): principal.ProfileInput(username=value)


def test_exact_frontend_contract_and_no_identity_payload():
    for name in ('Alice_01', 'abc', 'a' * 30):
        assert principal.ProfileInput(username=name).username == name
    for extra in ('subject', 'user_id', 'email', 'aal', 'verified'):
        with pytest.raises(ValidationError): principal.ProfileInput(username='Alice', **{extra: True})
    source = Path('frontend/src/profile-provisioning.js').read_text(encoding='utf-8')
    reserved = source.split('Object.freeze([', 1)[1].split('])', 1)[0]
    assert set(re.findall(r"'([a-z]+)'", reserved)) == principal.RESERVED_USERNAMES
