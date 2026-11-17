"""File-only runtime secrets and immutable reference; then existing native entry."""
import importlib.util
import os
from pathlib import Path
import sys
from app.native_secrets import runtime_environment


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
