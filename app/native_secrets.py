"""File-only operator secrets; shared with the retained Oracle image interface."""
from pathlib import Path
import stat


def runtime_environment(env, secret_root=Path('/run/secrets')):
    from app.native_release import load_settings
    values = dict(env)
    for variable, filename in [('MOVELLE_NATIVE_DATABASE_URL', 'native_database_url'),
                               ('MOVELLE_NATIVE_PUBLISHABLE_KEY', 'native_publishable_key')]:
        path = secret_root / filename
        if values.get(variable) or not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError
        with path.open(encoding='utf-8') as stream:
            raw = stream.read(8193)
        if not raw or len(raw) > 8192 or '\x00' in raw or '\n' in raw.rstrip('\r\n'):
            raise ValueError
        values[variable] = raw.rstrip('\r\n')
    config = load_settings(values)
    return values, config
