"""Explicit, target-guarded private schema operations; never called at startup."""
import os
import sys

from sqlalchemy.engine import make_url

from app import database
from app.migrations import check_schema, migrate
from app.private_config import load_settings


def initialize(command, env):
    try:
        if command not in {'check', 'migrate'}:
            raise ValueError
        runtime = make_url(load_settings(env).database_url)
        migration = make_url(env['MOVELLE_PRIVATE_MIGRATION_URL'])
        if (migration.username != 'movelle_private_stage23_migrator' or not migration.password
                or migration.set(username=runtime.username, password=runtime.password) != runtime):
            raise ValueError
        engine = database.create_database_engine(database_url=migration.render_as_string(hide_password=False))
        try:
            if command == 'migrate': migrate(engine)
            check_schema(engine)
        finally:
            engine.dispose()
    except Exception:
        raise RuntimeError('Private schema operation refused or unavailable') from None


if __name__ == '__main__':
    try:
        initialize(sys.argv[1] if len(sys.argv) == 2 else '', os.environ)
        print('Private schema 3 verified')
    except Exception:
        raise SystemExit('Private schema operation refused or unavailable') from None
