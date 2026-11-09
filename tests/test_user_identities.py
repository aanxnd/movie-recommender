"""Identity DDL and upgrades on isolated SQLite and optional loopback PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app import database, security
from app.migrations import check_schema, migrate
from app.models import GroupInvitation, RateBucket, SchemaVersion, User, UserIdentity
from test_postgresql_concurrency import pg_engine


@pytest.fixture(params=["sqlite", "postgresql"])
def identity_engine(request, tmp_path):
    if request.param == "postgresql":
        return request.getfixturevalue("pg_engine")
    engine = database.create_database_engine(tmp_path / "identities.db")
    request.addfinalizer(engine.dispose)
    migrate(engine)
    return engine


@pytest.mark.parametrize("old_version", [1, 2])
def test_upgrade_preserves_legacy_relationships_and_credentials(identity_engine, old_version):
    engine = identity_engine
    with Session(engine) as session, session.begin():
        session.add_all([User(id=42), User(id=43)])
        session.flush()
        if engine.dialect.name == "postgresql":
            # Explicit fixture IDs must advance the disposable sequence, as an import would.
            session.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), 43, true)"))
        database.register_movies(session, [10])
        database.save_rating(session, 42, 10, 3.25)
        token, _ = security.issue_credential(session, 42)
        invitation, _ = security.issue_invitation(session, 43)
    with engine.begin() as connection:
        UserIdentity.__table__.drop(connection)
        if old_version == 1:
            RateBucket.__table__.drop(connection)
        connection.execute(SchemaVersion.__table__.update().values(version=old_version))
    with pytest.raises(ValueError, match="migration required"):
        check_schema(engine)
    migrate(engine)
    migrate(engine)
    check_schema(engine)
    with Session(engine) as session, session.begin():
        assert session.get(SchemaVersion, 1).version == 3
        assert list(session.scalars(select(User.id).order_by(User.id))) == [42, 43]
        assert list(session.scalars(select(UserIdentity))) == []
        assert database.get_user_profile(session, 42) == {10: 3.25}
        assert security.authenticate(session, "Bearer " + token) == 42
        assert security.authorize_group(session, [42, 43], {43: invitation}, "Bearer " + token) == 42
        assert session.get(GroupInvitation, 43) is not None
        assert database.create_user(session).id > 43


def test_nullable_reservations_and_uuid_round_trip(identity_engine):
    subject = uuid4()
    with Session(identity_engine) as session, session.begin():
        ids = [database.create_user(session).id for _ in range(3)]
        session.add_all([UserIdentity(user_id=ids[0]), UserIdentity(user_id=ids[1]),
                        UserIdentity(user_id=ids[2], supabase_subject=subject, username="Alice_01")])
    with Session(identity_engine) as session:
        assert session.get(UserIdentity, ids[0]).supabase_subject is None
        assert session.get(UserIdentity, ids[1]).username is None
        assert session.get(UserIdentity, ids[2]).supabase_subject == subject
        assert session.get(UserIdentity, ids[2]).username == "Alice_01"


@pytest.mark.parametrize("duplicate", ["subject", "username", "user_id", "foreign_key"])
def test_database_rejects_duplicate_or_orphan_mapping(identity_engine, duplicate):
    subject = uuid4()
    with Session(identity_engine) as session, session.begin():
        first, second = [database.create_user(session).id for _ in range(2)]
        session.add(UserIdentity(user_id=first, supabase_subject=subject, username="Alice"))
    values = dict(user_id=second, supabase_subject=uuid4(), username="Other")
    if duplicate == "subject": values["supabase_subject"] = subject
    if duplicate == "username": values["username"] = "aLiCe"
    if duplicate == "user_id": values["user_id"] = first
    if duplicate == "foreign_key": values["user_id"] = 99999
    with pytest.raises(IntegrityError), identity_engine.begin() as connection:
        connection.execute(UserIdentity.__table__.insert().values(**values))


@pytest.mark.parametrize("name", ["", "ab", "a" * 31, " Alice", "alice ", "al.ice", "\u00c4lice", "\u0130user", "Alice\0other"])
def test_username_policy_enforced_without_python_validation(identity_engine, name):
    with Session(identity_engine) as session, session.begin():
        uid = database.create_user(session).id
    with pytest.raises(DBAPIError), identity_engine.begin() as connection:
        connection.execute(UserIdentity.__table__.insert().values(user_id=uid, username=name))


def test_subject_text_cannot_bypass_uuid_uniqueness(identity_engine):
    subject = uuid4()
    with Session(identity_engine) as session, session.begin():
        first, second = [database.create_user(session).id for _ in range(2)]
        session.add(UserIdentity(user_id=first, supabase_subject=subject))
    with pytest.raises(DBAPIError), identity_engine.begin() as connection:
        connection.execute(text("INSERT INTO user_identities (user_id, supabase_subject) VALUES (:id, :sub)"),
                           {"id": second, "sub": subject.hex.upper()})
    with pytest.raises(DBAPIError), identity_engine.begin() as connection:
        connection.execute(text("INSERT INTO user_identities (user_id, supabase_subject) VALUES (:id, :sub)"),
                           {"id": second, "sub": "g" * 32})
    if identity_engine.dialect.name == "sqlite":
        with pytest.raises(IntegrityError), identity_engine.begin() as connection:
            connection.execute(text("INSERT INTO user_identities (user_id, supabase_subject) VALUES (:id, :sub)"),
                               {"id": second, "sub": subject.hex + "\0suffix"})


def test_concurrent_case_collision_has_one_winner(identity_engine):
    with Session(identity_engine) as session, session.begin():
        ids = [database.create_user(session).id for _ in range(2)]
    def claim(pair):
        try:
            with identity_engine.begin() as connection:
                connection.execute(UserIdentity.__table__.insert().values(user_id=pair[0], username=pair[1]))
            return True
        except IntegrityError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(claim, zip(ids, ["CaseName", "cASEnAME"]))) == 1


def test_unversioned_identity_table_is_not_silently_adopted(identity_engine):
    with identity_engine.begin() as connection:
        connection.execute(SchemaVersion.__table__.update().values(version=2))
    with pytest.raises(ValueError, match="Unversioned identity"):
        migrate(identity_engine)
    with identity_engine.connect() as connection:
        assert connection.scalar(select(SchemaVersion.version)) == 2
        assert inspect(connection).has_table("user_identities")


def test_failed_upgrade_rolls_back_ddl_and_version(identity_engine, monkeypatch):
    with identity_engine.begin() as connection:
        UserIdentity.__table__.drop(connection)
        connection.execute(SchemaVersion.__table__.update().values(version=2))
    def fail(*args, **kwargs):
        raise RuntimeError("simulated version write failure")
    with monkeypatch.context() as patch:
        patch.setattr(SchemaVersion.__table__, "update", fail)
        with pytest.raises(RuntimeError, match="simulated"):
            migrate(identity_engine)
    with identity_engine.connect() as connection:
        assert connection.scalar(select(SchemaVersion.version)) == 2
        assert not inspect(connection).has_table("user_identities")
    migrate(identity_engine)
    check_schema(identity_engine)
