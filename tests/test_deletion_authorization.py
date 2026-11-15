"""Real local signatures, existing native policy and fictional password REST responses."""
from types import SimpleNamespace
from uuid import uuid4

from pydantic import SecretStr
import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import deletion_authorization as auth, provisioning_principal
from app.deletion_routes import compose_deletion_candidate
from app.deletion_store import DeletionUnavailable, intents, metadata
from app.models import User
from app.provisioning import provision_profile
from app.provisioning_principal import ProfileInput, ProvisioningPrincipal
from app.supabase_policy import AccessDenied, AccessUnavailable
from test_api import api_paths
from test_deletion_store import deletion, identity_engine, pg_engine, requested
from test_supabase_claims import evidence
from test_supabase_policy import account
from test_supabase_jwt import ORIGIN


@pytest.fixture
def authorizer(account, monkeypatch):
    e, policy, user, _ = account
    user['created_at'] = '2026-01-01T00:00:00Z'
    monkeypatch.setattr(auth, 'SupabaseAccessPolicy', lambda **_: policy)
    a = auth.DeletionAuthorizer(ORIGIN, 'sb_publishable_offline')
    calls, state = [], {'fail': None}
    def request(method, path, **kwargs):
        calls.append(path)
        if path.endswith('/challenge'):
            return 200, dict(id=str(uuid4()), type='totp', expires_at=e.now+100)
        if path.endswith('/verify'):
            if state['fail'] == 'totp': return 422, {'code': 'mfa_verification_failed'}
            claims = {'aal': 'aal2', 'amr': [{'method': 'password' if state['fail'] == 'totp-amr' else 'totp', 'timestamp': e.now-10}]}
            if state['fail'] == 'totp-subject': claims['sub'] = str(uuid4())
            if state['fail'] == 'totp-session': claims['session_id'] = str(uuid4())
            return 200, {'access_token': e.sign(claims),
                         'user': {'id': str(e.subject)}}
        if path.startswith('logout'):
            return (503 if state['fail'] == 'cleanup' else 204), {}
        assert kwargs['body'] == {'email': user['email'], 'password': 'synthetic-private'}
        if state['fail'] == 'password': return 400, {'msg': 'private diagnostics'}
        changes = {'session_id': str(uuid4())}
        if state['fail'] == 'foreign': changes['sub'] = str(uuid4())
        if state['fail'] == 'same-session': changes['session_id'] = str(e.session_id)
        token = e.sign(changes)
        if state['fail'] == 'factor-race': user['factors'] = [dict(id=str(uuid4()), factor_type='totp', status='verified')]
        return 200, {'access_token': token, 'user': {'id': changes.get('sub', str(e.subject))}}
    monkeypatch.setattr(a._transport, 'request', request)
    return e, a, user, calls, state


def test_fresh_password_receipt_is_short_lived_and_never_contains_credentials(authorizer):
    e, a, _, calls, _ = authorizer
    result = a.authorize(e.sign(), SecretStr('synthetic-private'))
    assert result.subject == e.subject and result.session_id == e.session_id
    assert result.expires_at <= e.now+121
    assert calls == ['token?grant_type=password', 'logout?scope=local']
    assert 'synthetic' not in repr(result)


@pytest.mark.parametrize('failure', ['password', 'foreign', 'same-session', 'cleanup', 'factor-race'])
def test_bad_security_evidence_never_issues_deletion_receipt(authorizer, failure):
    e, a, _, _, state = authorizer
    state['fail'] = failure
    with pytest.raises((AccessDenied, DeletionUnavailable)):
        a.authorize(e.sign(), SecretStr('synthetic-private'))


def test_enrolled_aal1_cannot_start_password_proof_but_aal2_can(authorizer):
    e, a, user, calls, _ = authorizer
    user['factors'] = [dict(id=str(uuid4()), factor_type='totp', status='verified')]
    with pytest.raises(AccessDenied): a.authorize(e.sign(), SecretStr('synthetic-private'))
    assert not calls
    with pytest.raises(AccessDenied):
        a.authorize(e.sign({'aal': 'aal2'}), SecretStr('synthetic-private'))
    from uuid import UUID
    assert a.authorize(e.sign({'aal': 'aal2'}), SecretStr('synthetic-private'),
        UUID(user['factors'][0]['id']), SecretStr('123456')).aal == 'aal2'


@pytest.mark.parametrize('failure', ['totp', 'totp-amr', 'totp-subject', 'totp-session'])
def test_historical_aal2_and_password_cannot_replace_fresh_totp_for_deletion(authorizer, failure):
    from uuid import UUID
    e, a, user, calls, state = authorizer
    factor = uuid4(); user['factors'] = [dict(id=str(factor), factor_type='totp', status='verified')]
    state['fail'] = failure
    with pytest.raises(AccessDenied):
        a.authorize(e.sign({'aal': 'aal2'}), SecretStr('synthetic-private'), factor, SecretStr('123456'))
    assert calls[-1].endswith('/verify')


def test_all_native_routes_and_provisioning_block_after_request_without_touching_another_owner(authorizer, identity_engine, api_paths):
    from fastapi.testclient import TestClient
    e, a, user, _, state = authorizer
    metadata.create_all(identity_engine)
    p = ProvisioningPrincipal(e.subject, e.session_id, e.now+600, 'aal1')
    uid = provision_profile(lambda: Session(identity_engine), p, ProfileInput(username='Owner')).user_id
    app = compose_deletion_candidate(signing_key=b'offline-test-key-only-'*2, reviewed=True,
        project_url=ORIGIN, publishable_key='sb_publishable_offline', audience='authenticated',
        origin='http://127.0.0.1:5173', prepared_dir=api_paths[0], database_url=identity_engine.url.render_as_string(hide_password=False))
    # Candidate constructor uses the same fixture policy; only its public-password transport is mocked.
    from app import deletion_provider
    # Patch the class method for the newly constructed candidate authorizer.
    original = a._transport.request
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(deletion_provider.AuthJsonTransport, 'request', lambda self, *args, **kwargs: original(*args, **kwargs))
        with TestClient(app) as client:
            headers = {'Authorization': 'Bearer ' + e.sign(), 'Origin': 'http://127.0.0.1:5173'}
            body = dict(request_id=str(uuid4()), password='synthetic-private', confirmation='PERMANENTLY DELETE MY ACCOUNT')
            assert client.post('/auth/deletion', headers=headers, json={**body, 'user_id': uid}).status_code == 422
            assert client.post('/auth/deletion', headers={**headers, 'Origin': 'https://evil.invalid'}, json=body).status_code == 403
            bad = client.post('/auth/deletion', headers={**headers, 'Authorization': 'Bearer ' + e.sign({'iss': 'https://evil.invalid'})}, json=body)
            assert bad.status_code == 401 and 'synthetic-private' not in bad.text
            state['fail'] = 'password'
            assert client.post('/auth/deletion', headers=headers, json=body).status_code == 401
            state['fail'] = None
            assert client.post('/auth/deletion', headers=headers, json=body).json() == {'status': 'pending'}
            assert client.post('/auth/deletion', headers=headers, json=body).status_code == 429
            for path in ['/users/me', f'/users/{uid}/ratings', '/auth/profile', '/auth/settings']:
                assert client.get(path, headers=headers).status_code == 401
            assert client.post('/auth/profile', headers=headers, json={'username': 'Reclaim'}).status_code == 401
            assert client.get('/movies/search?q=Film').status_code == 200
            user['id'] = str(uuid4())
            other = {'Authorization': 'Bearer ' + e.sign({'sub': user['id']})}
            assert client.get('/auth/profile', headers=other).json() == {'status': 'eligible'}
    with Session(identity_engine) as s: assert s.get(User, uid) is not None  # No worker/admin action from HTTP.


def test_missing_lifecycle_storage_cannot_fail_open(authorizer):
    e, a, _, _, _ = authorizer
    class Missing:
        issuer = a.issuer
        def blocked(self, _): raise RuntimeError('private SQL')
    policy = auth.DeletionAwarePolicy(a.policy, Missing())
    with pytest.raises(AccessUnavailable): policy.check(e.sign())


def test_expired_intent_requires_fresh_receipt_to_renew_the_same_request(deletion):
    store, p, *_ = deletion
    request = requested(deletion)
    with store.sessions() as s, s.begin():
        row = dict(s.execute(select(intents)).mappings().one()); row['authorized_until'] = 1
        s.execute(update(intents).values(authorized_until=1, authorization_tag=store._tag(row)))
    assert store.request(p, uuid4(), 'PERMANENTLY DELETE MY ACCOUNT') == request
    assert store.authorized(store.claim(request))


def test_candidate_has_no_automatic_entry_or_default_enable():
    with pytest.raises(DeletionUnavailable): compose_deletion_candidate(signing_key=b'fixture'*8)


def test_candidate_refuses_startup_without_reviewed_journal_schema(authorizer, identity_engine, api_paths):
    from fastapi.testclient import TestClient
    app = compose_deletion_candidate(signing_key=b'offline-test-key-only-'*2, reviewed=True,
        project_url=ORIGIN, publishable_key='sb_publishable_offline', audience='authenticated',
        origin='http://127.0.0.1:5173', prepared_dir=api_paths[0], database_url=identity_engine.url.render_as_string(hide_password=False))
    with pytest.raises(RuntimeError, match='Native preflight failed'):
        with TestClient(app): pass
    from sqlalchemy import inspect
    assert not inspect(identity_engine).has_table('account_deletion_intents')
    assert not app.state.initialized
