"""Owned compare-and-swap with real SQLite/PostgreSQL constraints and transactions."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from time import time
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import account_settings as service, database, security
from app.models import GroupInvitation, UserIdentity
from app.provisioning import provision_profile
from app.provisioning_principal import ProfileInput, ProvisioningPrincipal
from test_postgresql_concurrency import pg_engine
from test_user_identities import identity_engine
from test_provisioning_routes import setup_route
from test_supabase_policy import account
from test_supabase_claims import evidence
from test_supabase_jwt import ORIGIN


def fixture(engine, name='Alice'):
    p = ProvisioningPrincipal(uuid4(), uuid4(), int(time()) + 600, 'aal2')
    profile = provision_profile(lambda: Session(engine), p, ProfileInput(username=name))
    return p, profile.user_id


def operate(engine, principal, username=None, revision='1'):
    return service.profile_settings(lambda: Session(engine), principal,
        UsernameInput(username=username, revision=revision) if username is not None else None)


UsernameInput = service.UsernameInput


def test_rename_preserves_ownership_data_and_rejects_aba(identity_engine):
    p, uid = fixture(identity_engine)
    with Session(identity_engine) as session, session.begin():
        database.register_movies(session, [10])
        database.save_rating(session, uid, 10, 4.5)
        invitation, _ = security.issue_invitation(session, uid)
    assert operate(identity_engine, p) == dict(status='ready', username='Alice', revision='1')
    assert operate(identity_engine, p, 'Bob')['revision'] == '2'
    assert operate(identity_engine, p, 'Alice', '2')['revision'] == '3'
    with pytest.raises(HTTPException) as error:
        operate(identity_engine, p, 'Stale', '1')
    assert error.value.status_code == 409
    with Session(identity_engine) as session:
        assert session.get(UserIdentity, uid).supabase_subject == p.subject
        assert database.get_user_profile(session, uid) == {10: 4.5}
        assert session.get(GroupInvitation, uid).token_hash == security.token_hash(invitation)


def test_unique_conflict_and_cross_account_cannot_choose_owner(identity_engine):
    a, first = fixture(identity_engine)
    b, second = fixture(identity_engine, 'Other')
    with pytest.raises(HTTPException) as error:
        operate(identity_engine, b, 'ALICE')
    assert (error.value.status_code, error.value.detail) == (409, 'Username unavailable')
    assert operate(identity_engine, a)['revision'] == operate(identity_engine, b)['revision'] == '1'
    with pytest.raises(ValidationError):
        UsernameInput(username='NewName', revision='1', user_id=first)
    assert first != second
    operate(identity_engine, b, 'Different')
    assert operate(identity_engine, a)['username'] == 'Alice'


def test_concurrent_updates_only_one_wins(identity_engine):
    p, _ = fixture(identity_engine)
    def change(name):
        try:
            return operate(identity_engine, p, name)['status']
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(change, ['First', 'Second']), key=str) == [409, 'updated']
    assert operate(identity_engine, p)['revision'] == '2'


@pytest.mark.parametrize('revision', ['', '0', '-1', '01', '1.0', '９', '9223372036854775807', 1, None])
def test_invalid_revision_rejected(revision):
    with pytest.raises(ValidationError):
        UsernameInput(username='ValidName', revision=revision)


def test_unknown_expired_and_forged_principal_denied(identity_engine, caplog):
    p, _ = fixture(identity_engine)
    for principal in [replace(p, subject=uuid4()), replace(p, expires_at=0), {'subject': p.subject}]:
        with pytest.raises(HTTPException) as error:
            service.profile_settings(lambda: Session(identity_engine), principal)
        assert error.value.status_code == 401
        assert str(p.subject) not in str(error.value.detail) + caplog.text


def test_expiry_while_waiting_rolls_back_update(identity_engine, monkeypatch):
    p, _ = fixture(identity_engine)
    def expire(connection, cursor, statement, *args):
        if statement.startswith('UPDATE user_identities'):
            monkeypatch.setattr('app.provisioning_principal.time', lambda: p.expires_at + 1)
    event.listen(identity_engine, 'after_cursor_execute', expire)
    try:
        with pytest.raises(HTTPException) as error:
            operate(identity_engine, p, 'LateName')
        assert error.value.status_code == 401
    finally:
        event.remove(identity_engine, 'after_cursor_execute', expire)
        monkeypatch.undo()
    assert operate(identity_engine, p)['revision'] == '1'


def test_http_policy_origin_payload_and_legacy_boundaries(setup_route):
    from app.account_settings_routes import account_settings_router
    from app.main import app as legacy
    s = setup_route
    s.client.app.include_router(account_settings_router(project_url=ORIGIN, audience='authenticated',
        publishable_key='sb_publishable_offline', session_factory=lambda: Session(s.engine),
        origin='http://127.0.0.1:5173'))
    assert s.client.post('/auth/profile', headers=s.headers, json={'username': 'Alice'}).status_code == 200
    assert s.client.get('/auth/settings', headers=s.headers).json()['revision'] == '1'
    body = dict(username='NewName', revision='1')
    assert s.client.patch('/auth/settings', headers=s.headers, json=body).json()['revision'] == '2'
    assert s.client.patch('/auth/settings', headers=s.headers, json=body).status_code == 409
    for headers in [{}, {'Authorization': 'Bearer opaque-legacy'},
                    {**s.headers, 'Authorization': 'Bearer ' + s.evidence.sign()}]:
        assert s.client.patch('/auth/settings', headers=headers, json=body).status_code == 401
    assert s.client.patch('/auth/settings', headers={**s.headers, 'Origin': 'https://evil.invalid'}, json=body).status_code == 403
    bad = s.client.patch('/auth/settings', headers=s.headers, json={**body, 'user_id': 42})
    assert bad.status_code == 422 and bad.json() == {'detail': 'Invalid profile input'}
    assert bad.headers['cache-control'] == 'no-store'
    s.user['factors'] = None
    assert s.client.get('/auth/settings', headers=s.headers).status_code == 401
    assert '/auth/settings' not in [getattr(r, 'path', '') for r in legacy.routes]


@pytest.mark.parametrize('phase', ['before_commit', 'after_commit'])
def test_unknown_write_outcome_is_generic_and_never_retried(identity_engine, phase, caplog):
    p, _ = fixture(identity_engine)
    calls = []
    class Failing(Session):
        pass
    def fail(_):
        raise OperationalError('private SQL', {}, Exception('private database diagnostics'))
    def factory():
        session = Failing(identity_engine) if calls else Session(identity_engine)
        calls.append(session)
        if len(calls) == 2:
            event.listen(session, phase, fail)
        return session
    with pytest.raises(HTTPException) as error:
        service.profile_settings(factory, p, UsernameInput(username='MaybeChanged', revision='1'))
    assert error.value.status_code == 503 and len(calls) == 2
    assert 'private' not in error.value.detail + caplog.text
    observed = operate(identity_engine, p)
    assert observed['revision'] == ('1' if phase == 'before_commit' else '2')
