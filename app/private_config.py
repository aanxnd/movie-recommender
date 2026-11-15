"""Explicit private-preview targets; no production defaults or hosted discovery."""
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url

PROJECT = 'https://jsbulnrcxtvslvvxjizq.supabase.co'
PRODUCTION_BRANCH = 'br-tiny-bonus-b4ec6f9z'
PRODUCTION_API = 'https://movie-recommender-api.nicetree-0929c2a3.canadacentral.azurecontainerapps.io'


def origin(value):
    if not isinstance(value, str) or len(value) > 253:
        raise ValueError
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment or parsed.port is not None
            or not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*', parsed.hostname)
            or value != 'https://' + parsed.hostname):
        raise ValueError
    return value


@dataclass(frozen=True)
class PrivateSettings:
    frontend: str
    backend: str
    database_url: str = field(repr=False)
    gate: str = field(repr=False)
    publishable_key: str = field(repr=False)
    prepared_dir: str


def settings(env, targets):
    """Targets are an operator-reviewed file, never request/body/environment origins.

    Endpoint-to-branch ownership requires owner console verification before approval;
    PostgreSQL cannot independently attest a Neon control-plane branch identifier.
    """
    try:
        if (env.get('MOVELLE_PRIVATE_MODE') != 'private-stage23' or env.get('APP_ENV') != 'production'
                or env.get('TRUSTED_PROXY_IPS') or any(k.startswith('PG') and v for k, v in env.items())
                or targets.get('approved') is not True
                or targets['branch_name'] != 'private-stage23'
                or targets['azure_app'] != 'movie-recommender-api-private'
                or targets['supabase_url'] != PROJECT
                or not re.fullmatch(r'br-[a-z0-9-]+', targets['branch_id'])
                or targets['branch_id'] == PRODUCTION_BRANCH):
            raise ValueError
        frontend, backend = origin(targets['frontend_origin']), origin(targets['backend_origin'])
        if (frontend == backend or backend == PRODUCTION_API
                or not backend.removeprefix('https://').endswith('.azurecontainerapps.io')
                or env.get('CORS_ALLOWED_ORIGINS') != frontend):
            raise ValueError
        forbidden = targets['protected_database_hosts']
        host = targets['database_host']
        if (not isinstance(forbidden, list) or not forbidden or not all(isinstance(h, str) and h for h in forbidden)
                or host in {h.lower() for h in forbidden} or not re.fullmatch(r'ep-[a-z0-9-]+(?:\.[a-z0-9-]+)+\.neon\.tech', host)):
            raise ValueError
        url = make_url(env['MOVELLE_PRIVATE_DATABASE_URL'])
        if (url.drivername not in {'postgresql', 'postgresql+psycopg'} or url.host != host
                or url.port not in {None, 5432} or url.database != 'movelle_private_stage23'
                or url.username != 'movelle_private_stage23' or not url.password
                or dict(url.query) != {'sslmode': 'verify-full', 'sslrootcert': 'system', 'channel_binding': 'require'}):
            raise ValueError
        gate, key, prepared = (env[k] for k in ('MOVELLE_PRIVATE_GATE_SECRET',
            'MOVELLE_PRIVATE_PUBLISHABLE_KEY', 'MOVELLE_PRIVATE_PREPARED_DIR'))
        if (not re.fullmatch(r'[A-Za-z0-9_-]{43}', gate)
                or not re.fullmatch(r'sb_publishable_[A-Za-z0-9_-]{1,256}', key) or not prepared):
            raise ValueError
        return PrivateSettings(frontend, backend, url.render_as_string(hide_password=False), gate, key, prepared)
    except Exception:
        raise ValueError('Approved isolated private configuration required') from None


def load_settings(env):
    try:
        with open(env['MOVELLE_PRIVATE_TARGETS_FILE'], encoding='utf-8') as stream:
            raw = stream.read(8193)
        if len(raw) > 8192:
            raise ValueError
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError
                result[key] = value
            return result
        return settings(env, json.loads(raw, object_pairs_hook=unique))
    except Exception:
        raise ValueError('Approved isolated private configuration required') from None
