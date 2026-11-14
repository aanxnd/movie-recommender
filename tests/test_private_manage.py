"""Private deployment commands on a synthetic SQLite target; never hosted DDL."""
import json

import pytest
from sqlalchemy.engine import make_url

from app import database, private_manage
from app.migrations import check_schema
from test_private_boundary import private_inputs


@pytest.fixture
def migration_inputs(private_inputs, tmp_path):
    env, targets = private_inputs
    path = tmp_path / 'targets.json'; path.write_text(json.dumps(targets))
    env['MOVELLE_PRIVATE_TARGETS_FILE'] = str(path)
    env['MOVELLE_PRIVATE_MIGRATION_URL'] = make_url(env['MOVELLE_PRIVATE_DATABASE_URL']).set(
        username='movelle_private_stage23_migrator', password='synthetic-migration').render_as_string(hide_password=False)
    return env


def test_explicit_migration_is_guarded_idempotent_and_uses_separate_role(migration_inputs, tmp_path, monkeypatch):
    env = migration_inputs
    engine = database.create_database_engine(tmp_path / 'private-schema.db')
    def isolated(*, database_url):
        assert make_url(database_url) == make_url(env['MOVELLE_PRIVATE_MIGRATION_URL'])
        return engine
    monkeypatch.setattr(database, 'create_database_engine', isolated)
    private_manage.initialize('migrate', env)
    private_manage.initialize('check', env)
    private_manage.initialize('migrate', env)
    check_schema(engine)
    engine.dispose()


@pytest.mark.parametrize('change', ['host', 'role', 'database', 'tls', 'mode', 'command'])
def test_wrong_target_or_command_never_connects(migration_inputs, monkeypatch, change):
    env = migration_inputs
    url = make_url(env['MOVELLE_PRIVATE_MIGRATION_URL'])
    values = {'host': url.set(host='ep-production.neon.tech'), 'role': url.set(username='neondb_owner'),
        'database': url.set(database='neondb'), 'tls': url.set(query={'sslmode': 'require'})}
    if change in values: env['MOVELLE_PRIVATE_MIGRATION_URL'] = values[change].render_as_string(hide_password=False)
    if change == 'mode': env['MOVELLE_PRIVATE_MODE'] = 'production'
    monkeypatch.setattr(database, 'create_database_engine', lambda **_: pytest.fail('Wrong-target connection'))
    with pytest.raises(RuntimeError, match='^Private schema operation refused or unavailable$'):
        private_manage.initialize('reset' if change == 'command' else 'migrate', env)
