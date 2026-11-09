"""Real PG17 fixtures, never a hosted URL; proposed SQL is executable ONLY here."""
import os
from pathlib import Path
import re
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from test_postgresql import local_test_url


PROPOSAL = Path(__file__).resolve().parents[1] / 'docs/sql/auth_state_role_proposal.sql'
READER = 'movelle_auth_state_reader'
APIS = ('anon', 'authenticated', 'service_role', 'authenticator')
CALL = 'SELECT * FROM movelle_auth_private.observe_state(%s::pg_catalog.uuid,%s::pg_catalog.uuid)'


@pytest.fixture(scope='module')
def auth_cluster():
    if not os.environ.get('POSTGRES_TEST_URL'):
        pytest.skip('Disposable loopback PostgreSQL 17 not configured')
    parsed = local_test_url(os.environ['POSTGRES_TEST_URL']).set(drivername='postgresql')
    params = psycopg.conninfo.conninfo_to_dict(parsed.render_as_string(hide_password=False))
    created = []
    with psycopg.connect(**params, autocommit=True) as admin:
        assert 170000 <= admin.info.server_version < 180000
        assert admin.execute('SELECT rolsuper FROM pg_roles WHERE rolname=current_user').fetchone()[0]
        try:
            if not admin.execute("SELECT 1 FROM pg_roles WHERE rolname='postgres'").fetchone():
                admin.execute('CREATE ROLE postgres NOLOGIN CREATEROLE BYPASSRLS')
                created.append('postgres')
            for role in (*APIS, READER, 'movelle_fixture_plain_owner'):
                assert not admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,)).fetchone()
                if role == READER:
                    admin.execute(re.search(r'CREATE ROLE movelle_auth_state_reader.*?;',
                        PROPOSAL.read_text(encoding='utf-8'), flags=re.S)[0])
                else:
                    admin.execute(sql.SQL('CREATE ROLE {} NOLOGIN NOINHERIT').format(sql.Identifier(role)))
                created.append(role)
            # Synthetic definer only; NEVER grant this membership to runtime.
            admin.execute('GRANT pg_read_all_data TO movelle_fixture_plain_owner WITH INHERIT TRUE')
            yield params
        finally:
            for role in reversed(created):
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))


def install(connection, database):
    """Extract reviewed transaction, remove ONLY its offline interlock/role setup."""
    source = PROPOSAL.read_text(encoding='utf-8')
    assert source.strip().startswith('/*') and source.strip().endswith('*/')
    program = source.split('BEGIN;', 1)[1].split('ROLLBACK;', 1)[0]
    program, n = re.subn(r'DO \$guard\$.*?END; \$guard\$;', '', program, count=1, flags=re.S)
    assert n == 1
    program, n = re.subn(r'CREATE ROLE movelle_auth_state_reader.*?;', '', program, count=1, flags=re.S)
    assert n == 1  # The module fixture owns this cluster-wide NOLOGIN role.
    program = program.replace('"<privately_inspected_database>"', sql.Identifier(database).as_string(connection))
    connection.execute('SET ROLE postgres')
    try:
        connection.execute('BEGIN;' + program + 'COMMIT;')
    except Exception:
        connection.execute('ROLLBACK')
        raise
    finally:
        connection.execute('RESET ROLE')


@pytest.fixture
def auth_db(auth_cluster):
    name = 'movelle_auth_fixture_' + uuid4().hex
    params = {**auth_cluster, 'dbname': name}
    with psycopg.connect(**auth_cluster, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {} OWNER postgres').format(sql.Identifier(name)))
        try:
            with psycopg.connect(**params, autocommit=True) as c:
                c.execute('CREATE SCHEMA auth')
                c.execute('CREATE TABLE auth.users(id uuid PRIMARY KEY, banned_until timestamptz, deleted_at timestamptz)')
                c.execute('CREATE TABLE auth.sessions(id uuid PRIMARY KEY, user_id uuid REFERENCES auth.users, not_after timestamptz)')
                c.execute('ALTER TABLE auth.users ENABLE ROW LEVEL SECURITY')
                c.execute('ALTER TABLE auth.sessions ENABLE ROW LEVEL SECURITY')
                c.execute('GRANT USAGE ON SCHEMA auth TO postgres')
                c.execute('GRANT SELECT ON auth.users,auth.sessions TO postgres')
                c.execute('ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT EXECUTE ON FUNCTIONS TO anon,authenticated,service_role')
                install(c, name)
                subject, session, other = uuid4(), uuid4(), uuid4()
                c.execute('INSERT INTO auth.users(id) VALUES (%s),(%s)', (subject, other))
                c.execute('INSERT INTO auth.sessions(id,user_id) VALUES (%s,%s)', (session, subject))
            yield params, subject, session, other
        finally:
            assert re.fullmatch(r'movelle_auth_fixture_[0-9a-f]{32}', name)
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


def observe(db, subject=None, session=None, role=READER, readonly=True, setup=None, stale=False):
    params, default_subject, default_session, _ = db
    with psycopg.connect(**params, autocommit=True) as c:
        c.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(role)))
        if setup:
            c.execute(setup)
        with c.transaction():
            if stale:
                c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            elif readonly:
                c.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED READ ONLY')
            return c.execute(CALL, (subject or default_subject, session or default_session)).fetchall()


def mutate(db, command, values=None):
    with psycopg.connect(**db[0], autocommit=True) as c:
        c.execute(command, values)


def test_binding_and_fresh_reads(auth_db):
    rows = observe(auth_db)
    assert len(rows) == 1 and rows[0][:4] == (True, True, True, True)
    assert rows[0][4].utcoffset() is not None
    for subject, session in [(auth_db[3], auth_db[2]), (uuid4(), auth_db[2]), (auth_db[1], uuid4())]:
        assert observe(auth_db, subject, session)[0][:4] == (False,)*4
    mutate(auth_db, 'DELETE FROM auth.sessions')
    assert observe(auth_db)[0][:4] == (False,)*4


@pytest.mark.parametrize('command,index', [
    ('UPDATE auth.users SET deleted_at=now()', 1),
    ("UPDATE auth.users SET banned_until=now()+interval '1 hour'", 2),
    ("UPDATE auth.sessions SET not_after=now()-interval '1 second'", 3),
])
def test_rejected_markers(auth_db, command, index):
    mutate(auth_db, command)
    assert observe(auth_db)[0][index] is False


def test_past_ban_future_expiry_and_hard_delete(auth_db):
    mutate(auth_db, "UPDATE auth.users SET banned_until=now()-interval '1 hour'")
    mutate(auth_db, "UPDATE auth.sessions SET not_after=now()+interval '1 hour'")
    assert observe(auth_db)[0][:4] == (True,)*4
    mutate(auth_db, 'DELETE FROM auth.sessions; DELETE FROM auth.users')
    assert observe(auth_db)[0][:4] == (False,)*4


def test_rls_does_not_become_implicit_missing_state(auth_db):
    mutate(auth_db, 'ALTER FUNCTION movelle_auth_private.observe_state(uuid,uuid) OWNER TO movelle_fixture_plain_owner')
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='row-level security'):
        observe(auth_db)


@pytest.mark.parametrize('role', APIS)
def test_api_roles_cannot_invoke(auth_db, role):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        observe(auth_db, role=role)


@pytest.mark.parametrize('command', ['SELECT id FROM auth.users', 'SELECT id FROM auth.sessions',
    'CREATE TABLE movelle_auth_private.unsafe(id int)', 'SET ROLE postgres',
    'UPDATE auth.users SET deleted_at=now()'])
def test_runtime_privilege_isolation(auth_db, command):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        observe(auth_db, setup=command)


def test_hostile_search_path_and_claim_settings(auth_db):
    setup = """CREATE TEMP TABLE users(id uuid); CREATE TEMP TABLE sessions(id uuid);
        SET search_path=pg_temp,public; SET request.jwt.claim.sub='untrusted';"""
    assert observe(auth_db, setup=setup)[0][:4] == (True,)*4


def test_effective_execute_and_public_baseline(auth_db):
    with psycopg.connect(**auth_db[0], autocommit=True) as c:
        for role in (*APIS, 'movelle_fixture_plain_owner'):
            assert c.execute("SELECT has_function_privilege(%s, 'movelle_auth_private.observe_state(uuid,uuid)', 'EXECUTE')",
                             (role,)).fetchone() == (False,)
        assert c.execute("SELECT has_schema_privilege(%s,'auth','USAGE'), has_database_privilege(%s,current_database(),'TEMP')",
                         (READER, READER)).fetchone() == (False, True)
        assert c.execute("SELECT proconfig FROM pg_proc WHERE oid='movelle_auth_private.observe_state(uuid,uuid)'::regprocedure").fetchone()[0] == ['search_path=""', 'row_security=off']


def test_inconsistent_duplicate_binding_fails_closed(auth_db):
    mutate(auth_db, 'ALTER TABLE auth.users DROP CONSTRAINT users_pkey CASCADE')
    mutate(auth_db, 'INSERT INTO auth.users(id) VALUES (%s)', (auth_db[1],))
    assert observe(auth_db)[0][:4] == (False,)*4


def test_write_or_stale_transaction_rejected(auth_db):
    with pytest.raises(psycopg.errors.InvalidTransactionState):
        observe(auth_db, readonly=False)
    with pytest.raises(psycopg.errors.InvalidTransactionState):
        observe(auth_db, stale=True)


@pytest.mark.parametrize('field', [0, 1])
@pytest.mark.parametrize('value', [None, '00000000-0000-0000-0000-000000000000', 'malformed'])
def test_invalid_subject_or_session_rejected(auth_db, field, value):
    with psycopg.connect(**auth_db[0], autocommit=True) as c, c.transaction():
        c.execute('SET TRANSACTION READ ONLY')
        with pytest.raises((psycopg.errors.InvalidParameterValue, psycopg.errors.InvalidTextRepresentation)):
            values = [auth_db[1], auth_db[2]]
            values[field] = value
            c.execute(CALL, values)


def test_equal_absolute_expiry_is_denied(auth_db):
    # One protocol message shares statement_timestamp, with a new READ ONLY txn.
    with psycopg.connect(**auth_db[0], autocommit=True) as c, psycopg.ClientCursor(c) as cur:
        cur.execute('UPDATE auth.sessions SET not_after=statement_timestamp(); COMMIT; '
                    'SET SESSION AUTHORIZATION movelle_auth_state_reader; BEGIN READ ONLY; '
                    + CALL + '; COMMIT;', (auth_db[1], auth_db[2]))
        rows = None
        while True:
            if cur.description:
                rows = cur.fetchall()
            if not cur.nextset():
                break
        assert rows[0][0] is True and rows[0][3] is False


def test_unexpected_default_grantee_aborts_install(auth_db):
    with psycopg.connect(**auth_db[0], autocommit=True) as c:
        c.execute('DROP SCHEMA movelle_auth_private CASCADE')  # owned local fixture only
        c.execute('ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT EXECUTE ON FUNCTIONS TO movelle_fixture_plain_owner')
        with pytest.raises(psycopg.errors.RaiseException, match='Unexpected new-object ACL'):
            install(c, auth_db[0]['dbname'])
        assert c.execute("SELECT to_regnamespace('movelle_auth_private')").fetchone() == (None,)


@pytest.mark.parametrize('grant,revoke', [
    ('GRANT postgres TO anon WITH INHERIT FALSE, SET TRUE', 'REVOKE postgres FROM anon'),
    ('GRANT pg_read_all_data TO movelle_auth_state_reader WITH INHERIT FALSE, SET TRUE',
     'REVOKE pg_read_all_data FROM movelle_auth_state_reader'),
])
def test_privileged_set_paths_abort_install(auth_db, grant, revoke):
    with psycopg.connect(**auth_db[0], autocommit=True) as c:
        c.execute('DROP SCHEMA movelle_auth_private CASCADE')
        c.execute(grant)
        try:
            with pytest.raises(psycopg.errors.RaiseException, match='Unexpected role authority'):
                install(c, auth_db[0]['dbname'])
        finally:
            c.execute(revoke)
