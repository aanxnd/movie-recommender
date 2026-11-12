"""Legacy issuance/recovery cannot claim newly provisioned numeric identities."""
import sys
from time import time

from fastapi import HTTPException
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import database, manage, security
from app.models import Credential, GroupInvitation, UserIdentity
from test_postgresql_concurrency import pg_engine
from test_user_identities import identity_engine
from test_provisioning import caller, provision, counts
from test_api import api_paths
from app.main import create_app
from fastapi.testclient import TestClient


def test_no_legacy_issuance_for_new_profile(identity_engine, caplog):
    native = provision(identity_engine, caller())
    with Session(identity_engine) as session, session.begin():
        legacy = database.create_user(session).id
        token, _ = security.issue_credential(session, legacy)
    with Session(identity_engine) as session, session.begin():
        with pytest.raises(ValueError, match='^Legacy credential issuance is unavailable for this profile$'):
            security.issue_credential(session, native.user_id)
        with pytest.raises(HTTPException) as error:
            security.require_owner(session, native.user_id, 'Bearer ' + token)
        assert error.value.status_code == 403
        assert session.get(Credential, native.user_id) is None
        assert security.authenticate(session, 'Bearer ' + token) == legacy
    assert counts(identity_engine) == (2, 1, 1, 0, 0) and not caplog.records


@pytest.mark.parametrize('expired_credential', [False, True])
def test_operator_recovery_rolls_back_without_claiming_native_profile(identity_engine, tmp_path, monkeypatch, expired_credential):
    native = provision(identity_engine, caller())
    with Session(identity_engine) as session, session.begin():
        invitation, _ = security.issue_invitation(session, native.user_id)
        if expired_credential:
            # Artificial historical state must be preserved even on denial.
            session.add(Credential(user_id=native.user_id, token_hash='a' * 64, expires_at=1))
    monkeypatch.setattr(database, 'create_database_engine', lambda: identity_engine)
    monkeypatch.setattr('app.config.validate', lambda: None)
    output = tmp_path / 'private-test-output'
    monkeypatch.setattr(sys, 'argv', ['manage', 'recover-profile', '--user-id', str(native.user_id), '--output', str(output)])
    with pytest.raises(SystemExit, match='Operation failed'): manage.main()
    assert output.read_text() == ''
    with Session(identity_engine) as session:
        assert session.get(GroupInvitation, native.user_id).token_hash == security.token_hash(invitation)
        assert bool(session.get(Credential, native.user_id)) == expired_credential
        assert session.get(UserIdentity, native.user_id).username == 'Alice_01'


def test_nullable_identity_does_not_block_legacy_registration_or_restoration(identity_engine):
    with Session(identity_engine) as session, session.begin():
        user_id = database.create_user(session).id
        session.add(UserIdentity(user_id=user_id, username='ReservedLegacy'))
        session.flush()
        token, _ = security.issue_credential(session, user_id)
    with Session(identity_engine) as session:
        assert security.authenticate(session, 'Bearer ' + token) == user_id


def test_live_creation_remains_separate_from_native_provisioning(api_paths):
    application = create_app(*api_paths)
    with TestClient(application) as client:
        first, second = client.post('/users').json(), client.post('/users').json()
        assert first['id'] != second['id'] and security.TOKEN_PATTERN.fullmatch(first['token'])
        with Session(application.state.engine) as session:
            assert list(session.scalars(select(UserIdentity))) == []
            assert security.authenticate(session, 'Bearer ' + first['token']) == first['id']
        assert client.get('/auth/profile').status_code == 404
        assert client.post('/auth/profile', json={'username': 'Alice'}).status_code == 404
