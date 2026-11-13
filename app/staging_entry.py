"""Explicit local staging entry/init commands. Reads only dedicated staging inputs."""
import os
import sys

from app import database
from app.migrations import check_schema, migrate
from app.staging import create_staging_app
from app.staging_database import local_staging_url


def application():
    try:
        return create_staging_app(prepared_dir=os.environ['MOVELLE_STAGING_PREPARED_DIR'],
            database_url=os.environ['MOVELLE_STAGING_DATABASE_URL'],
            project_url=os.environ['MOVELLE_STAGING_SUPABASE_URL'],
            publishable_key=os.environ['MOVELLE_STAGING_PUBLISHABLE_KEY'])
    except Exception:
        raise RuntimeError('Explicit isolated staging configuration unavailable') from None


def initialize(command):
    if command not in {'init', 'check'}:
        raise ValueError
    url = local_staging_url(os.environ['MOVELLE_STAGING_DATABASE_URL'])
    engine = database.create_database_engine(database_url=url.render_as_string(hide_password=False))
    try:
        if command == 'init': migrate(engine)
        check_schema(engine)
    finally:
        engine.dispose()


if __name__ == '__main__':
    try:
        initialize(sys.argv[1] if len(sys.argv) == 2 else '')
        print('Isolated staging schema 3 verified')
    except Exception:
        raise SystemExit('Staging database operation failed; inspect private local configuration') from None
