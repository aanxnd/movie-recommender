"""Explicit local schema initialization/configuration, never hosted migration."""
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import staging_entry
from app.models import Base, SchemaVersion, User
from test_postgresql_concurrency import pg_engine


def test_explicit_local_init_and_check_never_create_profiles(pg_engine, monkeypatch):
    monkeypatch.setenv('MOVELLE_STAGING_DATABASE_URL', pg_engine.url.render_as_string(hide_password=False))
    with pg_engine.begin() as connection: Base.metadata.drop_all(connection)
    staging_entry.initialize('init')
    staging_entry.initialize('check')
    with Session(pg_engine) as session:
        assert session.get(SchemaVersion, 1).version == 3
        assert list(session.scalars(select(User))) == []


def test_missing_staging_inputs_never_use_production_environment(monkeypatch):
    for name in ['MOVELLE_STAGING_PREPARED_DIR', 'MOVELLE_STAGING_DATABASE_URL',
                 'MOVELLE_STAGING_SUPABASE_URL', 'MOVELLE_STAGING_PUBLISHABLE_KEY']:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('DATABASE_URL', 'private-production-fixture')
    with pytest.raises(RuntimeError, match='Explicit isolated staging configuration unavailable'):
        staging_entry.application()


def test_unknown_initializer_command_never_connects(monkeypatch):
    with pytest.raises(ValueError): staging_entry.initialize('drop')
