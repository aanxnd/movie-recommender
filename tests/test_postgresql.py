"""Optional real dialect coverage, restricted to disposable localhost PostgreSQL."""

import os
from ipaddress import ip_address
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, IntegrityError
from sqlalchemy.orm import Session

from app import database
from app.models import UserRating


def local_test_url(value):
    """Reject indirect destinations and pin local hostnames to loopback IPs."""
    try:
        parsed = make_url(value)
        if parsed.drivername not in {'postgresql', 'postgresql+psycopg'}:
            raise ValueError
        if parsed.host == 'localhost':
            address = '127.0.0.1'
        else:
            address = str(ip_address(parsed.host))
            if not ip_address(address).is_loopback:
                raise ValueError
        # Conservative allowlist: no libpq host/hostaddr/service/dbname overrides.
        if set(parsed.query) - {'sslmode', 'connect_timeout', 'application_name'}:
            raise ValueError
        if any(os.environ.get(name) for name in ('PGSERVICE', 'PGSERVICEFILE')):
            raise ValueError
        if not parsed.database or '=' in parsed.database or '://' in parsed.database:
            raise ValueError
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError
        query = dict(parsed.query)
        query['hostaddr'] = address
        return parsed.set(port=parsed.port or 5432, query=query)
    except (ArgumentError, ValueError, TypeError):
        raise ValueError('POSTGRES_TEST_URL must identify explicit disposable loopback PostgreSQL') from None


@pytest.mark.skipif(not os.environ.get('POSTGRES_TEST_URL'), reason='Optional disposable localhost PostgreSQL')
def test_postgresql_persistence_upserts_int64_and_transactions():
    try:
        parsed=local_test_url(os.environ['POSTGRES_TEST_URL'])
    except ValueError as error:
        pytest.fail(str(error),pytrace=False)
    url=parsed.render_as_string(hide_password=False)
    schema='stage11_'+uuid.uuid4().hex
    admin=database.create_database_engine(database_url=url)
    engine=None
    try:
        with admin.begin() as connection: connection.execute(text(f'CREATE SCHEMA {schema}'))
        # Transaction pooling is not used by this local disposable test server.
        query=dict(parsed.query)
        query['options']=f'-c search_path={schema}'
        engine=database.create_database_engine(database_url=parsed.set(query=query).render_as_string(hide_password=False))
        database.create_schema(engine)
        maximum=2**63-1
        with Session(engine) as session,session.begin():
            database.register_movies(session,[10,maximum])
            database.register_movies(session,[10,maximum])
            first=database.create_user(session).id
            second=database.create_user(session).id
            assert first!=second
            original=database.save_rating(session,first,maximum,1.)
            updated=database.save_rating(session,first,maximum,4.5)
            assert original is updated and updated.rating==4.5
        with pytest.raises(IntegrityError):
            with Session(engine) as session,session.begin():
                session.add(UserRating(user_id=999999,movie_id=10,rating=4.))
                session.flush()
        with pytest.raises(RuntimeError):
            with Session(engine) as session,session.begin():
                database.save_rating(session,first,maximum,2.)
                raise RuntimeError('rollback')
        with Session(engine) as session:
            assert database.get_user_profile(session,first)=={maximum:4.5}
            assert database.create_user(session).id not in {first,second}
    finally:
        if engine is not None: engine.dispose()
        with admin.begin() as connection: connection.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
        admin.dispose()


@pytest.mark.parametrize('url', [
    'invalid URL',
    'postgresql://postgres@localhost/disposable?host=remote.example.invalid&hostaddr=192.0.2.1',
    'postgresql://postgres@localhost/disposable?host=remote.example.invalid',
    'postgresql://postgres@localhost/disposable?hostaddr=192.0.2.1',
    'postgresql://postgres@localhost/disposable?service=production',
    'postgresql://postgres@localhost/disposable?servicefile=/private/services.conf',
    'postgresql://postgres@localhost/disposable?host=127.0.0.1&host=remote.example.invalid',
    'postgresql://postgres@localhost/disposable?dbname=postgresql://remote.example.invalid/prod',
    'postgresql://postgres@localhost/disposable?port=55432',
    'postgresql://postgres@remote.example.invalid/disposable',
    'postgresql://postgres@192.0.2.1/disposable',
    'postgresql:///disposable',
    'postgresql://postgres@localhost/host=remote.example.invalid',
])
def test_unsafe_postgresql_destinations_rejected_before_engine(url, monkeypatch):
    monkeypatch.setenv('POSTGRES_TEST_URL', url)
    monkeypatch.setattr(database, 'create_database_engine', lambda **kwargs: pytest.fail('Engine constructed'))
    with pytest.raises(pytest.fail.Exception, match='explicit disposable loopback'):
        test_postgresql_persistence_upserts_int64_and_transactions()


@pytest.mark.parametrize('name', ['PGSERVICE', 'PGSERVICEFILE'])
def test_service_environment_rejected_before_engine(name, monkeypatch):
    monkeypatch.setenv('POSTGRES_TEST_URL', 'postgresql://postgres@localhost/disposable')
    monkeypatch.setenv(name, 'synthetic-service')
    monkeypatch.setattr(database, 'create_database_engine', lambda **kwargs: pytest.fail('Engine constructed'))
    with pytest.raises(pytest.fail.Exception, match='explicit disposable loopback'):
        test_postgresql_persistence_upserts_int64_and_transactions()


@pytest.mark.parametrize('host,address', [('localhost','127.0.0.1'), ('127.0.0.1','127.0.0.1'), ('127.0.0.2','127.0.0.2'), ('[::1]','::1')])
def test_local_postgresql_destinations_pinned(host, address, monkeypatch):
    monkeypatch.delenv('PGSERVICE', raising=False)
    monkeypatch.delenv('PGSERVICEFILE', raising=False)
    monkeypatch.setenv('PGHOSTADDR', '192.0.2.1')
    parsed=local_test_url(f'postgresql://postgres@{host}:55432/disposable?sslmode=disable')
    engine=database.create_database_engine(database_url=parsed.render_as_string(hide_password=False))
    try:
        _, effective=engine.dialect.create_connect_args(engine.url)
        assert effective['hostaddr']==address
        assert effective['port']==55432 and effective['sslmode']=='disable'
    finally:
        engine.dispose()
