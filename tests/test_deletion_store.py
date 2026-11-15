"""Synthetic owned data only. DDL is installed solely in isolated fixtures."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from time import time
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app import database, security
from app.deletion_store import DeletionStore, DeletionUnavailable, events, intents, metadata
from app.models import User, UserIdentity
from app.provisioning import provision_profile
from app.provisioning_principal import ProfileInput, ProvisioningPrincipal
from test_postgresql_concurrency import pg_engine
from test_user_identities import identity_engine


ISSUER = 'https://' + 'a'*20 + '.supabase.co/auth/v1'


@pytest.fixture
def deletion(identity_engine):
    metadata.create_all(identity_engine)  # Disposable test schemas only; no app migration registration.
    principal = ProvisioningPrincipal(uuid4(), uuid4(), int(time())+300, 'aal2')
    store = DeletionStore(lambda: Session(identity_engine), ISSUER, b'offline-test-key-only-'*2)
    profile = provision_profile(store.sessions, principal, ProfileInput(username='AccountOwner'))
    with store.sessions() as session, session.begin():
        peer = database.create_user(session).id
        database.register_movies(session, [10])
        database.save_rating(session, profile.user_id, 10, 4)
        database.save_rating(session, peer, 10, 2)
        security.issue_invitation(session, profile.user_id)
    return store, principal, profile.user_id, peer, identity_engine


def requested(d):
    store, principal, *_ = d
    return store.request(principal, uuid4(), 'PERMANENTLY DELETE MY ACCOUNT')


def test_pending_blocks_reprovisioning_and_retries_keep_one_intent(deletion):
    store, principal, uid, peer, engine = deletion
    request = requested(deletion)
    assert store.blocked(principal.subject)
    assert store.request(principal, uuid4(), 'PERMANENTLY DELETE MY ACCOUNT') == request
    with Session(engine) as session:
        assert database.get_user_profile(session, uid) == {10: 4}
        assert database.get_user_profile(session, peer) == {10: 2}
        assert list(session.scalars(select(events.c.event))) == ['requested']


def test_local_deletion_requires_provider_absence_and_preserves_other_users(deletion):
    store, principal, uid, peer, engine = deletion
    job = store.claim(requested(deletion))
    with pytest.raises(DeletionUnavailable):
        store.finish(job)
    store.provider_absent(job)
    store.finish(job)
    assert store.blocked(principal.subject) and store.claim(job.request_id) is None
    with Session(engine) as session:
        assert session.get(User, uid) is None and session.get(UserIdentity, uid) is None
        assert database.get_user_profile(session, peer) == {10: 2}
        assert list(session.scalars(select(events.c.event))) == ['requested', 'claimed', 'provider_absent', 'complete']


def test_worker_claims_are_exclusive_and_stale_claim_cannot_finish(deletion):
    store, _, _, _, engine = deletion
    request = requested(deletion)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(store.claim, [request, request]))
    job = next(j for j in jobs if j)
    assert sum(j is not None for j in jobs) == 1
    with engine.begin() as connection:
        connection.execute(update(intents).values(lease_until=0))
    with pytest.raises(DeletionUnavailable):
        store.provider_absent(job)
    assert store.claim(request).worker != job.worker


@pytest.mark.parametrize('field', ['user_id', 'phase', 'issuer', 'authorized_until'])
def test_tampered_issuer_or_account_cannot_become_worker_authority(deletion, field):
    store, _, _, peer, engine = deletion
    request = requested(deletion)
    with engine.begin() as connection:
        replacement = {'user_id': peer, 'phase': 'provider_absent', 'issuer': ISSUER.replace('a', 'b'), 'authorized_until': 2**40}
        connection.execute(update(intents).values(**{field: replacement[field]}))
    with pytest.raises(DeletionUnavailable):
        store.claim(request)
    with Session(engine) as session:
        assert session.get(User, peer) is not None


def test_unexpected_dependency_rolls_back_every_local_delete(deletion):
    store, principal, uid, _, engine = deletion
    job = store.claim(requested(deletion)); store.provider_absent(job)
    with engine.begin() as c:
        c.execute(text('CREATE TABLE future_dependency (owner BIGINT REFERENCES users(id))'))
        c.execute(text('INSERT INTO future_dependency VALUES (:id)'), {'id': uid})
    with pytest.raises(IntegrityError):
        store.finish(job)
    with Session(engine) as session:
        assert database.get_user_profile(session, uid) == {10: 4}
        assert session.get(UserIdentity, uid).supabase_subject == principal.subject
        assert session.scalar(select(intents.c.phase)) == 'provider_absent'


def test_invalid_confirmation_and_expired_owner_never_request_deletion(deletion):
    store, principal, *_ = deletion
    for p, confirm in [(principal, True), ({'subject': principal.subject}, 'PERMANENTLY DELETE MY ACCOUNT'),
                       (replace(principal, expires_at=0), 'PERMANENTLY DELETE MY ACCOUNT')]:
        with pytest.raises((DeletionUnavailable, HTTPException)):
            store.request(p, uuid4(), confirm)
    assert not store.blocked(principal.subject)
