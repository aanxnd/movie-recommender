"""Explicit operator schema command; never startup, never legacy recovery/claiming."""
import os
from pathlib import Path
import stat
import sys

from sqlalchemy.engine import make_url
from app import database
from app.migrations import check_schema, migrate
from app.native_secrets import runtime_environment


def initialize(command, env, secret_root=Path('/run/secrets')):
    try:
        if command not in {'check', 'migrate'}:
            raise ValueError
        _, settings = runtime_environment(env, secret_root)
        runtime = make_url(settings['database_url'])
        path = secret_root / 'native_migration_url'
        if not stat.S_ISREG(path.lstat().st_mode): raise ValueError
        with path.open(encoding='utf-8') as stream: raw = stream.read(8193)
        if len(raw) > 8192 or '\n' in raw.rstrip('\r\n') or '\x00' in raw: raise ValueError
        migration = make_url(raw.rstrip('\r\n'))
        if (migration.username != 'movelle_native_migrator' or not migration.password
                or migration.set(username=runtime.username, password=runtime.password) != runtime):
            raise ValueError
        engine = database.create_database_engine(database_url=migration.render_as_string(hide_password=False))
        try:
            if command == 'migrate': migrate(engine)
            check_schema(engine)
        finally:
            engine.dispose()
    except Exception:
        raise RuntimeError('Native schema operation refused or unavailable') from None


if __name__ == '__main__':
    try:
        initialize(sys.argv[1] if len(sys.argv) == 2 else '', os.environ)
        print('Native schema verified')
    except Exception:
        raise SystemExit('Native schema operation refused or unavailable') from None
