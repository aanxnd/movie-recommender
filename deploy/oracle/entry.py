"""File-only runtime secrets and immutable reference; then existing native entry."""
import importlib.util
import os
from pathlib import Path
import stat
import sys


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
    config = load_settings(values)  # exact issuer/origin/Neon/TLS/role; no network
    return values, config


def main():
    try:
        if sys.argv[1:] != ['python', '-m', 'app.native_release']:
            raise ValueError
        values, config = runtime_environment(os.environ)
        spec = importlib.util.spec_from_file_location('oracle_reference', Path(__file__).with_name('oracle-reference.py'))
        reference = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reference)
        reference.verify(config['prepared_dir'])
    except Exception:
        raise SystemExit('Oracle native startup refused') from None
    os.execvpe(sys.executable, [sys.executable, '-m', 'app.native_release'], values)


if __name__ == '__main__':
    main()
