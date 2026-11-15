"""Actual pinned REST shapes with synthetic provider state; no hosted network."""
import io
import json
from uuid import uuid4

from pydantic import SecretStr
import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import deletion_provider as provider
from app.deletion_store import DeletionUnavailable, intents
from app.deletion_worker import DeletionWorker
from app.models import User
from test_deletion_store import deletion, identity_engine, pg_engine, requested, ISSUER


class Reply(io.BytesIO):
    def __init__(self, status, value):
        super().__init__(json.dumps(value).encode()); self.status = status


@pytest.fixture
def worker(deletion, monkeypatch):
    store, principal, uid, peer, engine = deletion
    state = dict(exists=True, fail=None, calls=[])
    class Opener:
        def open(self, request, timeout):
            assert request.full_url == ISSUER + '/admin/users/' + str(principal.subject)
            assert timeout == 3
            method = request.get_method(); state['calls'].append(method)
            if state['fail'] == 'timeout': raise TimeoutError('private diagnostics')
            if state['fail'] == 'rate': return Reply(429, {'msg': 'private'})
            if method == 'GET':
                if state['fail'] == 'foreign': return Reply(200, {'id': str(uuid4())})
                if state['fail'] == 'fake404': return Reply(404, {'code': 'route_not_found'})
                stamp = '2026-02-01T00:00:00Z' if state['fail'] == 'recreated' else principal.provider_created_at
                return Reply(200, {'id': str(principal.subject), 'created_at': stamp}) if state['exists'] else Reply(404, {'code': 'user_not_found'})
            assert json.loads(request.data) == {'should_soft_delete': False}
            if state['fail'] == 'storage': return Reply(400, {'msg': 'storage owner'})
            state['exists'] = False
            if state['fail'] == 'lost-delete': raise TimeoutError('private committed response')
            return Reply(200, {})
    monkeypatch.setattr(provider, 'build_opener', lambda *args: Opener())
    eraser = provider.SupabaseIdentityEraser(ISSUER.removesuffix('/auth/v1'), SecretStr('synthetic-admin-only'), reviewed=True)
    return DeletionWorker(store, eraser, reviewed=True), state, requested(deletion), deletion


def test_identity_then_atomic_local_cleanup_and_idempotent_retry(worker):
    w, state, request, (store, p, uid, peer, engine) = worker
    assert w.run(request) == 'complete' and w.run(request) == 'unchanged'
    assert state['calls'] == ['GET', 'DELETE', 'GET']
    with Session(engine) as session:
        assert session.get(User, uid) is None and session.get(User, peer) is not None
    assert store.blocked(p.subject)


@pytest.mark.parametrize('failure', ['timeout', 'rate', 'foreign', 'fake404', 'storage', 'lost-delete', 'recreated'])
def test_failed_or_unknown_provider_outcomes_never_erase_local_data(worker, failure, caplog):
    w, state, request, (store, p, uid, peer, engine) = worker
    state['fail'] = failure
    with pytest.raises(DeletionUnavailable) as error: w.run(request)
    assert str(error.value) == 'Account deletion unavailable'
    assert 'private' not in caplog.text and 'synthetic-admin' not in repr(w)
    with Session(engine) as session: assert session.get(User, uid) is not None
    state['fail'] = None
    assert w.run(request) == 'complete'
    assert state['calls'].count('DELETE') == (2 if failure == 'storage' else 1)


def test_provider_deleted_neon_failure_resumes_without_repeating_delete(worker, monkeypatch):
    w, state, request, (store, p, uid, peer, engine) = worker
    original = store.finish
    monkeypatch.setattr(store, 'finish', lambda _: (_ for _ in ()).throw(RuntimeError('private Neon')))
    with pytest.raises(DeletionUnavailable): w.run(request)
    with Session(engine) as session:
        assert session.get(User, uid) is not None
        assert session.scalar(select(intents.c.phase)) == 'provider_absent'
    monkeypatch.setattr(store, 'finish', original)
    assert w.run(request) == 'complete' and state['calls'].count('DELETE') == 1


def test_consumed_phase_cannot_delete_a_recreated_identity(worker):
    w, state, request, (store, *_) = worker
    job = store.claim(request); store.provider_absent(job); store.release(job)
    with pytest.raises(DeletionUnavailable): w.run(request)
    assert state['calls'] == ['GET']


def test_expired_authorization_never_starts_provider_delete(worker):
    w, state, request, (store, *_) = worker
    with store.sessions() as s, s.begin():
        row = dict(s.execute(select(intents)).mappings().one()); row['authorized_until'] = 1
        s.execute(update(intents).values(authorized_until=1, authorization_tag=store._tag(row)))
    with pytest.raises(DeletionUnavailable): w.run(request)
    assert state['calls'] == ['GET']


def test_admin_capability_requires_review_and_pinned_tls_before_network():
    with pytest.raises(DeletionUnavailable):
        provider.SupabaseIdentityEraser(ISSUER, SecretStr('synthetic-admin-only'))
    with pytest.raises(DeletionUnavailable):
        provider.SupabaseIdentityEraser('http://foreign.invalid', SecretStr('synthetic-admin-only'), reviewed=True)


def test_expiry_tampering_after_claim_cannot_authorize_provider_delete(worker, monkeypatch):
    w, state, request, (store, *_) = worker
    original = w._provider._transport.request
    def changed(*args, **kwargs):
        reply = original(*args, **kwargs)
        with store.sessions() as s, s.begin():
            s.execute(update(intents).values(authorized_until=2**40))
        return reply
    monkeypatch.setattr(w._provider._transport, 'request', changed)
    with pytest.raises(DeletionUnavailable): w.run(request)
    assert state['calls'] == ['GET']


@pytest.mark.parametrize('raw', [b'private malformed', b'{"code":"user_not_found","code":"other"}', b' ' * 65537])
def test_malformed_or_oversized_provider_evidence_is_never_absence(monkeypatch, raw):
    class Opener:
        def open(self, request, timeout):
            reply = io.BytesIO(raw); reply.status = 404; return reply
    monkeypatch.setattr(provider, 'build_opener', lambda *args: Opener())
    transport = provider.AuthJsonTransport(ISSUER.removesuffix('/auth/v1'), SecretStr('synthetic-admin-only'))
    with pytest.raises(DeletionUnavailable) as error:
        transport.request('GET', 'admin/users/' + str(uuid4()))
    assert str(error.value) == 'Account deletion unavailable'
