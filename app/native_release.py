"""Separate native release entry. Existing Azure production command is unchanged."""
import json
import os
import re
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url

from app.account_settings_routes import account_settings_router
from app.native_app import compose_native_app


def settings(env, targets):
    try:
        if (env.get('APP_ENV') != 'production' or env.get('MOVELLE_NATIVE_MODE') != 'native-release'
                or targets.get('approved') is not True or env.get('TRUSTED_PROXY_IPS')
                or any(k.startswith('PG') and v for k, v in env.items())):
            raise ValueError
        origin = targets['frontend_origin']
        parsed = urlsplit(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.netloc != parsed.hostname
                or parsed.path or parsed.query or parsed.fragment or '*' in origin
                or origin != 'https://' + parsed.hostname
                or env.get('CORS_ALLOWED_ORIGINS') != origin):
            raise ValueError
        project = targets['supabase_url']
        if not re.fullmatch(r'https://[a-z0-9]{20}\.supabase\.co', project):
            raise ValueError
        url = make_url(env['MOVELLE_NATIVE_DATABASE_URL'])
        if (not re.fullmatch(r'ep-[a-z0-9-]+(?:\.[a-z0-9-]+)+\.neon\.tech', targets['database_host'])
                or url.drivername not in {'postgresql', 'postgresql+psycopg'}
                or url.host != targets['database_host'] or url.database != targets['database_name']
                or not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', targets['database_name'])
                or url.username != 'movelle_native' or not url.password or url.port not in {None, 5432}
                or dict(url.query) != {'sslmode': 'verify-full', 'sslrootcert': 'system', 'channel_binding': 'require'}):
            raise ValueError
        key, prepared = env['MOVELLE_NATIVE_PUBLISHABLE_KEY'], env['MOVELLE_NATIVE_PREPARED_DIR']
        if not re.fullmatch(r'sb_publishable_[A-Za-z0-9_-]{1,256}', key) or not prepared:
            raise ValueError
        return dict(origin=origin, project_url=project, audience='authenticated', publishable_key=key,
                    database_url=url.render_as_string(hide_password=False), prepared_dir=prepared)
    except Exception:
        raise ValueError('Approved native release configuration required') from None


def load_settings(env):
    try:
        from app.supabase_jwt import _unique_object
        with open(env['MOVELLE_NATIVE_TARGETS_FILE'], encoding='utf-8') as stream:
            raw = stream.read(8193)
        if len(raw) > 8192:
            raise ValueError
        return settings(env, json.loads(raw, object_pairs_hook=_unique_object))
    except Exception:
        raise ValueError('Approved native release configuration required') from None


def application():
    try:
        values = load_settings(os.environ)
        app = compose_native_app(**values)
        app.router.routes = [r for r in app.routes if getattr(r, 'path', None) not in
                            {'/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc'}]
        from sqlalchemy.orm import Session
        app.include_router(account_settings_router(project_url=values['project_url'], audience=values['audience'],
            publishable_key=values['publishable_key'], session_factory=lambda: Session(app.state.engine),
            origin=values['origin']))
        return app
    except Exception:
        raise RuntimeError('Native application configuration unavailable') from None


def main():
    import uvicorn
    try:
        app = application()
        port = int(os.environ.get('PORT', '8000'))
        if not 1 <= port <= 65535:
            raise ValueError
    except Exception:
        raise SystemExit('Native application startup refused') from None
    uvicorn.run(app, host='0.0.0.0', port=port, workers=1, reload=False, access_log=False,
                proxy_headers=False, forwarded_allow_ips='', limit_concurrency=64, timeout_graceful_shutdown=30)


if __name__ == '__main__':
    main()
