"""Real PostgreSQL concurrency and deadlines; disposable loopback schemas only."""
from concurrent.futures import ThreadPoolExecutor
import os
import uuid

import pytest
from sqlalchemy import text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import database, limits
from app.models import User
from test_postgresql import local_test_url


@pytest.fixture
def pg_engine():
    if not os.environ.get('POSTGRES_TEST_URL'):
        pytest.skip('Disposable loopback PostgreSQL not configured')
    parsed = local_test_url(os.environ['POSTGRES_TEST_URL'])
    admin = database.create_database_engine(database_url=parsed.render_as_string(hide_password=False))
    schema = 'verify_' + uuid.uuid4().hex
    engine = None
    try:
        with admin.begin() as c: c.execute(text(f'CREATE SCHEMA {schema}'))
        engine = database.create_database_engine(database_url=parsed.set(query={**dict(parsed.query), 'options': f'-c search_path={schema}'}).render_as_string(hide_password=False))
        database.create_schema(engine)
        yield engine
    finally:
        if engine is not None: engine.dispose()
        with admin.begin() as c: c.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
        admin.dispose()


def test_pg_concurrent_admission_quota_and_upserts(pg_engine):
    from fastapi import HTTPException
    with Session(pg_engine) as session, session.begin():
        uid = database.create_user(session).id
        database.register_movies(session, [1, 2])
    def write(movie):
        try:
            with Session(pg_engine) as session, session.begin():
                # Same short transaction: must not check out a nested connection.
                database.get_user(session, uid)
                limits.owner_admission(session, uid, 'write', 60)
                database.enforce_rating_quota(session, uid, movie, 1)
                database.save_rating(session, uid, movie, 4)
            return True
        except HTTPException:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(write, [1, 2])) == 1
    with Session(pg_engine) as session:
        assert len(database.get_user_profile(session, uid)) == 1


def test_pg_execution_and_lock_deadlines_recover_connections(pg_engine):
    with Session(pg_engine) as session, session.begin():
        uid = database.create_user(session).id
    with pg_engine.begin() as held:
        held.execute(update(User).where(User.id == uid).values(id=User.id))
        with pytest.raises(OperationalError):
            with pg_engine.begin() as blocked:
                blocked.execute(update(User).where(User.id == uid).values(id=User.id))
    with pytest.raises(OperationalError):
        with pg_engine.begin() as connection: connection.execute(text('SELECT pg_sleep(6)'))
    with pg_engine.begin() as connection:
        assert connection.execute(text('SELECT 1')).scalar_one() == 1
        assert connection.execute(text('SHOW statement_timeout')).scalar_one() == '5s'
        assert connection.execute(text('SHOW idle_in_transaction_session_timeout')).scalar_one() == '10s'
        assert connection.execute(text('SHOW transaction_timeout')).scalar_one() == '10s'


def test_pg_two_migrators_share_transaction_lock(pg_engine):
    # Only this fixture's unique disposable schema is cleared, never public tables.
    from app.models import Base
    with pg_engine.begin() as connection:
        Base.metadata.drop_all(connection)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(database.create_schema, [pg_engine, pg_engine]))


def test_pg_shared_rate_counter_allows_exactly_the_quota(pg_engine):
    from fastapi import HTTPException
    def enter(index):
        try:
            with Session(pg_engine) as session, session.begin():
                limits.consume(session, 'same-browser', 'concurrent', 3, 60, now=120)
            return True
        except HTTPException as e:
            assert e.status_code == 429
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(enter, range(12))) == 3


def test_pg_concurrent_profile_creation_cannot_exceed_lifetime_capacity(pg_engine):
    from fastapi import HTTPException
    def create(index):
        try:
            with Session(pg_engine) as session, session.begin():
                database.enforce_user_capacity(session, 2)
                database.create_user(session)
            return True
        except HTTPException as error:
            assert error.status_code == 503
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(create, range(8))) == 2
