"""Schema-3 upgrade rehearsal; isolated SQLite and loopback PostgreSQL only."""
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import database, security
from app.migrations import check_schema, migrate
from app.models import GroupInvitation, SchemaVersion, UserIdentity
from test_postgresql_concurrency import pg_engine
from test_user_identities import identity_engine


def old_schema(engine):
    subject = uuid4()
    with Session(engine) as session, session.begin():
        uid = database.create_user(session).id
        database.register_movies(session, [10])
        database.save_rating(session, uid, 10, 4.5)
        credential, _ = security.issue_credential(session, uid)
        invitation, _ = security.issue_invitation(session, uid)
    with engine.begin() as connection:
        UserIdentity.__table__.drop(connection)
        kind = 'UUID' if engine.dialect.name == 'postgresql' else 'CHAR(32)'
        connection.execute(text(f'CREATE TABLE user_identities (user_id BIGINT PRIMARY KEY REFERENCES users(id), '
                                f'supabase_subject {kind} UNIQUE, username VARCHAR(30))'))
        connection.execute(text('CREATE UNIQUE INDEX uq_identity_username_ci ON user_identities (lower(username))'))
        connection.execute(text('INSERT INTO user_identities VALUES (:uid, :subject, :name)'),
                           dict(uid=uid, subject=str(subject) if kind == 'UUID' else subject.hex, name='Original'))
        connection.execute(SchemaVersion.__table__.update().values(version=3))
    return uid, subject, credential, invitation


def test_v3_upgrade_preserves_ids_data_and_adds_durable_revision(identity_engine):
    uid, subject, credential, invitation = old_schema(identity_engine)
    with pytest.raises(ValueError, match='migration required'):
        check_schema(identity_engine)
    migrate(identity_engine)
    migrate(identity_engine)
    check_schema(identity_engine)
    with Session(identity_engine) as session:
        identity = session.get(UserIdentity, uid)
        assert (identity.supabase_subject, identity.username, identity.profile_revision) == (subject, 'Original', 1)
        assert database.get_user_profile(session, uid) == {10: 4.5}
        assert security.authenticate(session, 'Bearer ' + credential) == uid
        assert security.authorize_group(session, [uid], {}, 'Bearer ' + credential) == uid
        assert session.get(GroupInvitation, uid).token_hash == security.token_hash(invitation)
    for revision in (0, -1, None):
        with pytest.raises(IntegrityError), identity_engine.begin() as connection:
            connection.execute(UserIdentity.__table__.update().values(profile_revision=revision))


def test_v3_failure_rolls_back_column_and_version(identity_engine, monkeypatch):
    old_schema(identity_engine)
    def fail(*args, **kwargs):
        raise RuntimeError('synthetic version failure')
    with monkeypatch.context() as patch:
        patch.setattr(SchemaVersion.__table__, 'update', fail)
        with pytest.raises(RuntimeError, match='synthetic'):
            migrate(identity_engine)
    with identity_engine.connect() as connection:
        assert connection.scalar(select(SchemaVersion.version)) == 3
    migrate(identity_engine)
    check_schema(identity_engine)
