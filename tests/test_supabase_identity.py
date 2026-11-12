"""Read-only identity resolution against real isolated schemas, without hosted auth."""
from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, OperationalError
from sqlalchemy.orm import Session

from app import database, security
from app.models import Credential, GroupInvitation, User, UserIdentity, UserRating
from app.supabase_identity import (
    AuthenticatedIdentity, IdentityResolutionUnavailable, UnresolvedIdentity, resolve_verified_subject,
)
from test_postgresql_concurrency import pg_engine
from test_supabase_jwt import setup as jwt_setup


@pytest.fixture(params=["sqlite", "postgresql"])
def engine(request, tmp_path):
    if request.param == "postgresql":
        return request.getfixturevalue("pg_engine")
    value = database.create_database_engine(tmp_path / "resolution.db")
    request.addfinalizer(value.dispose)
    database.create_schema(value)
    return value


@pytest.fixture
def linked(engine):
    first, second = uuid4(), uuid4()
    with Session(engine) as session, session.begin():
        session.add_all([User(id=104), User(id=207), User(id=308)])
        session.flush()
        session.add_all([UserIdentity(user_id=104, supabase_subject=first, username="First"),
                        UserIdentity(user_id=207, supabase_subject=second, username="Second"),
                        UserIdentity(user_id=308, username="Legacy")])
    return first, second


def test_distinct_subjects_resolve_only_their_existing_numeric_ids(engine, linked):
    with Session(engine) as session, session.begin():
        for subject, expected in zip(linked, [104, 207]):
            identity = resolve_verified_subject(session, subject)
            assert identity == AuthenticatedIdentity(subject=subject, user_id=expected)
            assert str(subject) not in repr(identity) and "user_id=" not in repr(identity)
            with pytest.raises(FrozenInstanceError): identity.user_id = 308
        assert session.in_transaction()


def test_trusted_verifier_output_composes_without_duplicating_crypto(engine, linked, jwt_setup):
    verifier, sign, *_ = jwt_setup
    subject = verifier.verify(sign({"sub": str(linked[0])}))
    with Session(engine) as session:
        assert resolve_verified_subject(session, subject).user_id == 104


@pytest.mark.parametrize("reservation", [True, False])
def test_unknown_and_unlinked_fail_without_creating_or_claiming(engine, linked, reservation, caplog):
    with Session(engine) as session, session.begin():
        if not reservation:
            session.execute(delete(UserIdentity).where(UserIdentity.user_id == 308))
    with Session(engine) as session:
        counts = [session.scalar(select(func.count()).select_from(model)) for model in (User, UserIdentity)]
        with pytest.raises(UnresolvedIdentity, match="^Identity could not be resolved$"):
            resolve_verified_subject(session, uuid4())
        assert counts == [session.scalar(select(func.count()).select_from(model)) for model in (User, UserIdentity)]
        assert session.get(UserIdentity, 308) is None or session.get(UserIdentity, 308).supabase_subject is None
    assert not caplog.records


@pytest.mark.parametrize("subject", [None, True, 104, 1.5, b"subject", "not-a-uuid", str(uuid4()),
    "First", "email@example.invalid", {"sub": str(uuid4())}, UUID(int=0), UUID(int=2**128 - 1)])
def test_invalid_subject_types_never_reach_database(engine, monkeypatch, subject):
    with Session(engine) as session:
        monkeypatch.setattr(session, "execute", lambda *args: pytest.fail("Untrusted input reached database"))
        with pytest.raises(UnresolvedIdentity, match="^Identity could not be resolved$"):
            resolve_verified_subject(session, subject)


def test_deleted_link_and_user_are_rejected(engine, linked):
    with Session(engine) as session, session.begin():
        session.execute(delete(UserIdentity).where(UserIdentity.user_id == 104))
        session.execute(delete(User).where(User.id == 104))
    with Session(engine) as session:
        with pytest.raises(UnresolvedIdentity): resolve_verified_subject(session, linked[0])
        assert resolve_verified_subject(session, linked[1]).user_id == 207


def test_foreign_key_prevents_deleting_a_linked_user(engine, linked):
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(delete(User).where(User.id == 104))
    with Session(engine) as session:
        assert resolve_verified_subject(session, linked[0]).user_id == 104


def test_no_autoflush_and_no_stale_orm_mapping_or_transaction_control(engine, linked):
    pending_subject = uuid4()
    with Session(engine) as session:
        mapping = session.get(UserIdentity, 104)
        mapping.supabase_subject = uuid4()
        pending_user = User(id=999)
        pending_link = UserIdentity(user_id=999, supabase_subject=pending_subject)
        session.add_all([pending_user, pending_link])
        assert resolve_verified_subject(session, linked[0]).user_id == 104
        with pytest.raises(UnresolvedIdentity): resolve_verified_subject(session, pending_subject)
        assert pending_user in session.new and pending_link in session.new and mapping in session.dirty
        assert session.in_transaction()
    with Session(engine) as session:
        assert session.get(User, 999) is None
        assert resolve_verified_subject(session, linked[0]).user_id == 104


@pytest.mark.parametrize("invalid_id", [0, -1])
def test_invalid_local_id_is_not_a_valid_application_identity(engine, invalid_id):
    subject = uuid4()
    with Session(engine) as session, session.begin():
        session.add(User(id=invalid_id))
        session.flush()
        session.add(UserIdentity(user_id=invalid_id, supabase_subject=subject))
    with Session(engine) as session:
        with pytest.raises(UnresolvedIdentity): resolve_verified_subject(session, subject)


def test_resolution_preserves_ratings_credentials_and_group_invitations(engine, linked):
    with Session(engine) as session, session.begin():
        database.register_movies(session, [10])
        database.save_rating(session, 104, 10, 3.25)
        # Deliberately seed a historical credential predating the link. New
        # issuance is forbidden; read-only resolution must not revoke old state.
        token = 'x' * 43
        session.add(Credential(user_id=104, token_hash=security.token_hash(token), expires_at=2**62))
        invitation, _ = security.issue_invitation(session, 207)
    with Session(engine) as session, session.begin():
        before = (session.get(Credential, 104).token_hash, session.get(GroupInvitation, 207).token_hash)
        assert resolve_verified_subject(session, linked[0]).user_id == 104
        assert database.get_user_profile(session, 104) == {10: 3.25}
        assert security.authenticate(session, "Bearer " + token) == 104
        assert security.authorize_group(session, [104, 207], {207: invitation}, "Bearer " + token) == 104
        with pytest.raises(UnresolvedIdentity): resolve_verified_subject(session, token)
        assert before == (session.get(Credential, 104).token_hash, session.get(GroupInvitation, 207).token_hash)
        assert session.scalar(select(func.count()).select_from(UserRating)) == 1
        assert list(session.scalars(select(User.id).order_by(User.id))) == [104, 207, 308]


@pytest.mark.parametrize("ambiguous", [True, False])
def test_ambiguous_results_and_database_errors_are_sanitized(engine, linked, monkeypatch, caplog, ambiguous):
    failure = MultipleResultsFound("private record details") if ambiguous else OperationalError(
        "private SQL", {"subject": str(linked[0])}, Exception("private database diagnostics"))
    def fail(*args): raise failure
    with Session(engine) as session:
        monkeypatch.setattr(session, "execute", fail)
        expected = UnresolvedIdentity if ambiguous else IdentityResolutionUnavailable
        with pytest.raises(expected) as error: resolve_verified_subject(session, linked[0])
        assert str(error.value) == ("Identity could not be resolved" if ambiguous else "Identity resolution unavailable")
        assert str(linked[0]) not in str(error.value) and "private" not in str(error.value)
        assert error.value.__suppress_context__
    assert not caplog.records


def test_orphan_is_rejected_despite_cached_user_in_deliberately_corrupted_sqlite(tmp_path):
    # Only this disposable DB bypasses its FK temporarily to simulate pre-existing corruption.
    value = database.create_database_engine(tmp_path / "corrupt.db")
    subject = uuid4()
    try:
        database.create_schema(value)
        with Session(value) as session, session.begin():
            session.add(User(id=104))
            session.flush()
            session.add(UserIdentity(user_id=104, supabase_subject=subject))
        with Session(value) as session:
            cached_user = session.get(User, 104)
            with value.connect() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
                connection.execute(delete(User).where(User.id == 104))
                connection.commit()
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()
            assert session.get(User, 104) is cached_user
            with pytest.raises(UnresolvedIdentity): resolve_verified_subject(session, subject)
    finally:
        value.dispose()
