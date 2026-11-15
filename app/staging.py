"""Explicit local staging guard; never accepts production configuration."""
from app import config
from app.native_app import compose_native_app
from app.staging_database import local_staging_url

ORIGIN = 'http://127.0.0.1:5173'

def create_staging_app(*, prepared_dir, database_url, project_url, publishable_key, audience='authenticated'):
    if config.production():
        raise ValueError('Local staging cannot use production mode')
    url = local_staging_url(database_url)
    return _create_native_app(prepared_dir=prepared_dir, database_url=url.render_as_string(hide_password=False),
        project_url=project_url, publishable_key=publishable_key, audience=audience, origin=ORIGIN)

def _create_native_app(**kwargs):
    return compose_native_app(**kwargs, title='Movelle isolated local staging',
        preflight_error='Staging preflight failed; privately verify the isolated database schema')
