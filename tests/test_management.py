import json
import sys
import time

import pytest
from sqlalchemy.orm import Session
from app import database, manage, security
from app.models import Credential


def test_operator_recovery_preserves_ratings_and_refuses_active_credentials(tmp_path, monkeypatch):
    path = tmp_path / 'recovery.db'
    engine = database.create_database_engine(path)
    database.create_schema(engine)
    with Session(engine) as session, session.begin():
        uid = database.create_user(session).id
        database.register_movies(session, [1])
        database.save_rating(session, uid, 1, 3.25)
    monkeypatch.setattr(database, 'create_database_engine', lambda: engine)
    output = tmp_path / 'private.credentials.json'
    monkeypatch.setattr(sys, 'argv', ['manage', 'recover-profile', '--user-id', str(uid), '--output', str(output)])
    manage.main()
    recovered = json.loads(output.read_text())
    with Session(engine) as session:
        assert security.authenticate(session, 'Bearer ' + recovered['token']) == uid
        assert database.get_user_profile(session, uid) == {1: 3.25}
    second = tmp_path / 'second.credentials.json'
    monkeypatch.setattr(sys, 'argv', ['manage', 'recover-profile', '--user-id', str(uid), '--output', str(second)])
    with pytest.raises(SystemExit): manage.main()
    with Session(engine) as session, session.begin(): session.get(Credential, uid).expires_at = int(time.time()) - 1
    third = tmp_path / 'third.credentials.json'
    monkeypatch.setattr(sys, 'argv', ['manage', 'recover-profile', '--user-id', str(uid), '--output', str(third)])
    manage.main()
    assert json.loads(third.read_text())['token'] != recovered['token']
