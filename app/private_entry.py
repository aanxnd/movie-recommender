"""Explicit private process only; never imported by the production runtime."""
import os

from app.private_config import PROJECT, load_settings
from app.private_gate import PrivateGate
from app.staging import _create_native_app


def application():
    try:
        s = load_settings(os.environ)
        app = _create_native_app(prepared_dir=s.prepared_dir, database_url=s.database_url,
            project_url=PROJECT, publishable_key=s.publishable_key, audience='authenticated', origin=s.frontend)
        app.title = 'Movelle private owner preview'
        app.router.routes = [r for r in app.routes if getattr(r, 'path', None) not in
            {'/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc'}]
        app.add_middleware(PrivateGate, secret=s.gate, frontend=s.frontend, backend=s.backend)
        return app
    except Exception:
        raise RuntimeError('Private application configuration unavailable') from None


def main():
    import uvicorn
    try:
        app = application()
        port = int(os.environ.get('PORT', '8000'))
        if not 1 <= port <= 65535:
            raise ValueError
    except Exception:
        raise SystemExit('Private application startup refused') from None
    uvicorn.run(app, host='0.0.0.0', port=port, workers=1, reload=False, access_log=False,
        log_level='warning', proxy_headers=False, forwarded_allow_ips='',
        limit_concurrency=64, timeout_graceful_shutdown=30)


if __name__ == '__main__':
    main()
