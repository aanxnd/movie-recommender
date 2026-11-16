import pytest
from sqlalchemy.engine import make_url

from app import database
from app.migrations import check_schema
from deploy.oracle import manage
from test_oracle_image import secrets


@pytest.fixture
def migration_inputs(secrets):
    env, root = secrets
    runtime = make_url((root / 'native_database_url').read_text())
    url = runtime.set(username='movelle_native_migrator', password='synthetic-migration')
    (root / 'native_migration_url').write_text(url.render_as_string(hide_password=False))
    return env, root, url


def test_explicit_native_migration_is_idempotent_and_uses_a_separate_exact_role(migration_inputs, tmp_path, monkeypatch):
    env, root, expected = migration_inputs
    engine = database.create_database_engine(tmp_path / 'synthetic.db')
    def isolated(*, database_url):
        assert make_url(database_url) == expected
        return engine
    monkeypatch.setattr(database, 'create_database_engine', isolated)
    for command in ['migrate', 'check', 'migrate']: manage.initialize(command, env, root)
    check_schema(engine)
    engine.dispose()


@pytest.mark.parametrize('change', ['host', 'role', 'database', 'tls', 'mode', 'command',
    'missing', 'directory', 'oversized', 'multiline'])
def test_wrong_target_role_or_command_never_connects(migration_inputs, monkeypatch, change):
    env, root, url = migration_inputs
    file = root / 'native_migration_url'
    values = {'host': url.set(host='ep-unapproved.neon.tech'), 'role': url.set(username='postgres'),
        'database': url.set(database='unapproved'), 'tls': url.set(query={'sslmode': 'require'})}
    if change in values: file.write_text(values[change].render_as_string(hide_password=False))
    if change == 'mode': env['MOVELLE_NATIVE_MODE'] = 'legacy'
    if change == 'missing': file.unlink()
    if change == 'directory': file.unlink(); file.mkdir()
    if change == 'oversized': file.write_text('x' * 8193)
    if change == 'multiline': file.write_text('secret\nother-secret')
    monkeypatch.setattr(database, 'create_database_engine', lambda **_: pytest.fail('Wrong-target connection'))
    with pytest.raises(RuntimeError, match='^Native schema operation refused or unavailable$'):
        manage.initialize('reset' if change == 'command' else 'migrate', env, root)
