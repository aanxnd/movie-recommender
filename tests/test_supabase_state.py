"""Real local signatures + PG17; hosted connections replaced BEFORE observer calls."""
from dataclasses import FrozenInstanceError
import traceback

import psycopg
import pytest

from app import supabase_state as auth
from test_auth_state_sql import auth_cluster, auth_db, mutate, READER
from test_supabase_claims import evidence
from test_supabase_jwt import ORIGIN


DSN = f'host=db.{ORIGIN.removeprefix("https://")} dbname=postgres user={READER} password=synthetic-only sslmode=verify-full sslrootcert=system'


@pytest.fixture
def observer(auth_db, evidence, monkeypatch):
    original = psycopg.connect
    with original(**auth_db[0], autocommit=True) as c:
        c.execute('SET SESSION AUTHORIZATION movelle_auth_state_reader')
        approved = auth._catalog_digest(c.execute(auth._CATALOG).fetchall())
    calls = []
    def connect(**params):
        if params.get('host') == 'db.' + ORIGIN.removeprefix('https://'):
            assert params['user'] == READER and params['sslmode'] == 'verify-full'
            calls.append('local-only')
            c = original(**auth_db[0], autocommit=True)
            c.execute('SET SESSION AUTHORIZATION movelle_auth_state_reader')
            return c
        # Fixture mutations use ONLY the already-validated loopback connection.
        assert params['host'] == auth_db[0]['host'] and params['dbname'] == auth_db[0]['dbname']
        return original(**params)
    monkeypatch.setattr(auth.psycopg, 'connect', connect)
    monkeypatch.setattr(auth, 'SupabaseTokenVerifier', lambda *a, **kw: evidence.verifier)
    instance = auth.SupabaseStateObserver(ORIGIN, database_url=DSN, approved_catalog_sha256=approved)
    token = evidence.sign({'sub':str(auth_db[1]), 'session_id':str(auth_db[2])})
    assert calls == []
    return instance, token, calls


def unavailable(observer, token=None):
    with pytest.raises(auth.AuthenticationEvidenceUnavailable, match='^Authentication evidence unavailable$') as caught:
        observer[0].observe(token or observer[1])
    return caught.value


def test_bound_immutable_uncached_observations(observer, auth_db):
    instance, token, calls = observer
    first, second = instance.observe(token), instance.observe(token)
    assert first.claims.subject == auth_db[1] and first.claims.session_id == auth_db[2]
    assert first.issuer == ORIGIN+'/auth/v1' and first.nonce != second.nonce
    assert (first.binding_present, first.deletion_clear, first.ban_clear, first.absolute_expiry_clear) == (True,)*4
    assert calls == ['local-only']*2
    assert not hasattr(first,'is_active') and not hasattr(first,'account_state')
    assert str(auth_db[1]) not in repr(first)
    with pytest.raises(FrozenInstanceError): first.binding_present = False
    mutate(auth_db,'DELETE FROM auth.sessions')
    assert instance.observe(token).binding_present is False


@pytest.mark.parametrize('changes', [{'iss':'https://wrong.example.invalid/auth/v1'}, {'aud':'wrong'}, {'exp':1}])
def test_invalid_jwt_never_connects(observer, evidence, changes):
    with pytest.raises(auth.AuthenticationEvidenceDenied):
        observer[0].observe(evidence.sign(changes))
    assert observer[2] == []


def test_caller_claims_or_modified_signature_not_evidence(observer):
    for value in ({'sub':'client','active':True}, observer[1][:-10]+'tampered000'):
        with pytest.raises(auth.AuthenticationEvidenceDenied): observer[0].observe(value)
    assert observer[2] == []


@pytest.mark.parametrize('command', [
    'GRANT SELECT ON auth.users TO PUBLIC',
    'GRANT USAGE ON SCHEMA auth TO PUBLIC',
    'GRANT EXECUTE ON FUNCTION movelle_auth_private.observe_state(uuid,uuid) TO anon',
    'ALTER FUNCTION movelle_auth_private.observe_state(uuid,uuid) SET search_path=public',
    'CREATE SCHEMA fixture_extension; GRANT USAGE ON SCHEMA fixture_extension TO PUBLIC',
    'ALTER DEFAULT PRIVILEGES GRANT SELECT ON TABLES TO PUBLIC',
])
def test_permission_or_definition_drift_denies(observer, auth_db, command):
    mutate(auth_db, command)
    unavailable(observer)


@pytest.mark.parametrize('command', ['GRANT SELECT ON auth.users TO movelle_auth_state_reader',
    'GRANT CREATE ON SCHEMA public TO movelle_auth_state_reader',
    'GRANT EXECUTE ON FUNCTION movelle_auth_private.observe_state(uuid,uuid) TO PUBLIC'])
def test_known_unsafe_grants_cannot_be_approved_by_a_digest(observer, auth_db, command):
    mutate(auth_db,command)
    with psycopg.connect(**auth_db[0],autocommit=True) as c:
        c.execute('SET SESSION AUTHORIZATION movelle_auth_state_reader')
        observer[0]._approved = auth._catalog_digest(c.execute(auth._CATALOG).fetchall())
    unavailable(observer)  # Hard constraints remain independent of the snapshot.


def test_actual_broad_session_rejected(observer, monkeypatch, auth_db):
    original = psycopg.Connection.connect
    monkeypatch.setattr(auth.psycopg, 'connect', lambda **kw: original(**auth_db[0], autocommit=True))
    unavailable(observer)  # Session owner is admin, not runtime, despite approved digest.


@pytest.mark.parametrize('projection', [
    'true,true,true,1,pg_catalog.clock_timestamp()',
    'true,true,true,true,NULL',
    "true,true,true,true,pg_catalog.clock_timestamp()+interval '1 day'",
    'true,true,true,true,pg_catalog.clock_timestamp() FROM pg_catalog.pg_sleep(1)',
    'true,true,true,true,pg_catalog.clock_timestamp() FROM pg_catalog.generate_series(1,2)',
])
def test_malformed_future_or_timed_out_observation_denied(observer, monkeypatch, projection):
    monkeypatch.setattr(auth, '_CALL', 'SELECT '+projection+' WHERE %s::uuid IS NOT NULL AND %s::uuid IS NOT NULL')
    unavailable(observer)


def test_network_failure_redaction_and_slot_recovery(observer, monkeypatch, auth_db, caplog):
    connect = auth.psycopg.connect
    def broken(**kw): raise OSError(observer[1]+' synthetic-only '+str(auth_db[1]))
    monkeypatch.setattr(auth.psycopg, 'connect', broken)
    error = unavailable(observer)
    output = ''.join(traceback.format_exception(error))+caplog.text+str(error)
    assert all(secret not in output for secret in (observer[1], 'synthetic-only', str(auth_db[1])))
    monkeypatch.setattr(auth.psycopg,'connect',connect)
    assert observer[0].observe(observer[1]).binding_present


def test_ambient_override_busy_and_elapsed_deadline_denied(observer, monkeypatch):
    monkeypatch.setenv('PGHOSTADDR','192.0.2.1')
    unavailable(observer)
    assert observer[2] == []
    monkeypatch.delenv('PGHOSTADDR')
    observer[0]._slot.acquire()
    try: unavailable(observer)
    finally: observer[0]._slot.release()
    assert observer[2] == []
    times = iter([0,4])
    monkeypatch.setattr(auth,'monotonic',lambda: next(times))
    unavailable(observer)


def test_no_row_denied(observer, monkeypatch):
    monkeypatch.setattr(auth,'_CALL','SELECT true,true,true,true,pg_catalog.clock_timestamp() '
                        'WHERE %s::uuid IS NULL AND %s::uuid IS NULL')
    unavailable(observer)


@pytest.mark.parametrize('change', [
    'host=remote.example.invalid', 'hostaddr=127.0.0.1', 'service=untrusted',
    'options=-csearch_path=public', 'user=postgres', 'sslmode=require', 'dbname=host=remote',
])
def test_unsafe_configuration_rejected_without_io(change, monkeypatch):
    def forbidden(**kw): pytest.fail('Unexpected connection')
    monkeypatch.setattr(auth.psycopg,'connect',forbidden)
    with pytest.raises(ValueError,match='^Invalid server-only Auth-state configuration$'):
        auth.SupabaseStateObserver(ORIGIN,database_url=DSN+' '+change,approved_catalog_sha256='0'*64)


def test_no_unapproved_fingerprint_or_oversize_catalog(monkeypatch):
    for approved in (None,'','client-asserted', '0'*63):
        with pytest.raises(ValueError):
            auth.SupabaseStateObserver(ORIGIN,database_url=DSN,approved_catalog_sha256=approved)
    for rows in ([], [('x','y')]*5001, [('x','y'*2097152)]):
        with pytest.raises(ValueError): auth._catalog_digest(rows)
