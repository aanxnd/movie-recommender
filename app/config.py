"""Fail closed on production misconfiguration, without printing connection URLs."""

import os
from sqlalchemy.engine import make_url


def production() -> bool:
    mode = os.environ.get('APP_ENV', 'development')
    if mode not in {'development', 'production'}:
        raise ValueError('APP_ENV must be development or production')
    return mode == 'production'


def validate(database_url=None, database_path=None):
    if not production():
        return
    try:
        url = make_url(database_url or os.environ.get('DATABASE_URL', ''))
        if database_path is not None or url.get_backend_name() != 'postgresql':
            raise ValueError
        if url.query.get('sslmode') not in {'require', 'verify-ca', 'verify-full'}:
            raise ValueError
    except Exception:
        raise ValueError('Production requires PostgreSQL DATABASE_URL with TLS enabled') from None
    origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
    if not origins or any(not value.strip().startswith('https://') for value in origins.split(',')):
        raise ValueError('Production requires exact HTTPS CORS_ALLOWED_ORIGINS')
    if '*' in os.environ.get('TRUSTED_PROXY_IPS', ''):
        raise ValueError('TRUSTED_PROXY_IPS must not trust every caller')
