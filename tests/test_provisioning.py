"""Real schema transactions, uniqueness, preservation and uncertain outcomes."""
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from dataclasses import replace
import multiprocessing
from time import time
from uuid import uuid4

from fastapi import HTTPException
import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.orm import Session

from app import database, provisioning as service, security
from app.models import Credential, GroupInvitation, User, UserIdentity, UserRating
from app.provisioning_principal import ProfileInput, ProvisioningPrincipal
from test_postgresql_concurrency import pg_engine
from test_user_identities import identity_engine


def caller(subject=None):
    return ProvisioningPrincipal(subject or uuid4(), uuid4(), int(time()) + 600, 'aal2')


def provision(engine, principal, name='Alice_01', **kwargs):
    return service.provision_profile(lambda: Session(engine), principal, ProfileInput(username=name), **kwargs)


def counts(engine):
    with Session(engine) as session:
        return tuple(session.scalar(select(func.count()).select_from(model))
                     for model in (User, UserIdentity, Credential, UserRating, GroupInvitation))


def test_atomic_idempotent_minimal_initialization(identity_engine):
    p = caller()
    assert service.inspect_profile(lambda: Session(identity_engine), p) is None
    first = provision(identity_engine, p)
    for name in ('Alice_01', 'DifferentName'):
        assert provision(identity_engine, p, name) == first
    assert first.user_id > 0 and first.username == 'Alice_01'
    assert counts(identity_engine) == (1, 1, 0, 0, 0)


def test_conflict_rollback_preserves_legacy_data_and_no_linking(identity_engine):
    with Session(identity_engine) as session, session.begin():
        legacy = database.create_user(session).id
        token, expiry = security.issue_credential(session, legacy)
        invitation, _ = security.issue_invitation(session, legacy)
        database.register_movies(session, [10])
        database.save_rating(session, legacy, 10, 4)
    first = provision(identity_engine, caller(), 'Alice')
    for name in ('Alice', 'ALICE', 'alice'):
        with pytest.raises(HTTPException) as error: provision(identity_engine, caller(), name)
        assert error.value.status_code == 409 and 'Alice' not in error.value.detail
    assert counts(identity_engine) == (2, 1, 1, 1, 1)
    assert first.user_id != legacy
    with Session(identity_engine) as session:
        assert session.get(UserIdentity, legacy) is None
        assert security.authenticate(session, 'Bearer ' + token) == legacy
        assert session.get(Credential, legacy).expires_at == expiry
        assert session.get(GroupInvitation, legacy).token_hash == security.token_hash(invitation)
        assert database.get_user_profile(session, legacy) == {10: 4}


def test_capacity_existing_subject_still_resolves(identity_engine):
    p = caller()
    first = provision(identity_engine, p, maximum=1)
    assert provision(identity_engine, p, 'OtherName', maximum=1) == first
    with pytest.raises(HTTPException) as error: provision(identity_engine, caller(), maximum=1)
    assert error.value.status_code == 503 and counts(identity_engine) == (1, 1, 0, 0, 0)


@pytest.mark.parametrize('phase', ['before', 'after'])
def test_disconnect_and_uncertain_commit_use_clean_read(identity_engine, phase):
    p, attempts = caller(), []
    class Failing(Session):
        pass
    def fail(_): raise OperationalError('private SQL', {}, Exception('private diagnostics'))
    def factory():
        session = Failing(identity_engine) if not attempts else Session(identity_engine)
        if not attempts: event.listen(session, phase + '_commit', fail)
        attempts.append(session)
        return session
    if phase == 'before':
        with pytest.raises(HTTPException) as error:
            service.provision_profile(factory, p, ProfileInput(username='Alice'))
        assert error.value.status_code == 503 and counts(identity_engine) == (0, 0, 0, 0, 0)
    else:
        result = service.provision_profile(factory, p, ProfileInput(username='Alice'))
        assert provision(identity_engine, p, 'NewName') == result
        assert counts(identity_engine) == (1, 1, 0, 0, 0)
    assert len(attempts) == 2 and all(not s.in_transaction() for s in attempts)


def test_failed_identity_insert_rolls_back_user(identity_engine, monkeypatch, caplog):
    def fail(session):
        if any(isinstance(row, UserIdentity) for row in session.new):
            raise IntegrityError('private SQL', {}, Exception('secret'))
    def listener(session, *_): fail(session)
    event.listen(Session, 'before_flush', listener)
    try:
        with pytest.raises(HTTPException) as error: provision(identity_engine, caller())
    finally:
        event.remove(Session, 'before_flush', listener)
    assert error.value.status_code == 503 and counts(identity_engine) == (0, 0, 0, 0, 0)
    assert 'secret' not in error.value.detail + caplog.text


def test_expiry_and_untrusted_input_never_mutate(identity_engine):
    with pytest.raises(HTTPException) as error: provision(identity_engine, replace(caller(), expires_at=1))
    assert error.value.status_code == 401
    with pytest.raises(HTTPException): provision(identity_engine, {'subject': str(uuid4())})
    assert counts(identity_engine) == (0, 0, 0, 0, 0)


def test_inconsistent_existing_mapping_never_gets_repaired(identity_engine):
    p = caller()
    with Session(identity_engine) as session, session.begin():
        user = database.create_user(session)
        session.add(UserIdentity(user_id=user.id, supabase_subject=p.subject, username=None))
    with pytest.raises(HTTPException) as error: provision(identity_engine, p)
    assert error.value.status_code == 503 and counts(identity_engine) == (1, 1, 0, 0, 0)


def test_expiry_before_commit_rolls_back_both_rows(identity_engine, monkeypatch):
    checks = []
    def fresh(self):
        checks.append(True)
        if len(checks) > 1: raise HTTPException(401, 'Invalid authentication credentials')
    monkeypatch.setattr(ProvisioningPrincipal, 'require_fresh', fresh)
    with pytest.raises(HTTPException): provision(identity_engine, caller())
    assert counts(identity_engine) == (0, 0, 0, 0, 0)


def test_pg_parallel_subject_and_username_races(pg_engine):
    p = caller()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda i: provision(pg_engine, p, 'Name_' + str(i), maximum=1), range(8)))
    assert len({r.user_id for r in results}) == len({r.username for r in results}) == 1
    assert counts(pg_engine) == (1, 1, 0, 0, 0)
    def competing(name):
        try: return provision(pg_engine, caller(), name)
        except HTTPException as e:
            assert e.status_code == 409
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(competing, ['Conflict', 'CONFLICT']))
    assert sum(r is not None for r in results) == 1 and counts(pg_engine) == (2, 2, 0, 0, 0)


def process_create(url, subject, name):
    # Fresh engine/session in each spawned Python process, not a shared pool.
    from uuid import UUID
    engine = database.create_database_engine(database_url=url)
    try: return provision(engine, caller(UUID(subject)), name).user_id
    finally: engine.dispose()


def test_pg_separate_processes_share_subject_constraint(pg_engine):
    url, subject = pg_engine.url.render_as_string(hide_password=False), str(uuid4())
    with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context('spawn')) as pool:
        futures = [pool.submit(process_create, url, subject, name) for name in ('First', 'Second')]
        assert len({f.result(timeout=40) for f in futures}) == 1
    assert counts(pg_engine) == (1, 1, 0, 0, 0)


def test_lost_http_acknowledgement_and_read_vs_create(pg_engine):
    p = caller()
    provision(pg_engine, p)  # Response lost; the caller never receives this result.
    with ThreadPoolExecutor(max_workers=2) as pool:
        read = pool.submit(service.inspect_profile, lambda: Session(pg_engine), p)
        retry = pool.submit(provision, pg_engine, p, 'DifferentName')
        assert read.result() == retry.result()
    assert counts(pg_engine) == (1, 1, 0, 0, 0)
