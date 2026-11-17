"""Native Azure entry: immutable baked reference, no bootstrap or startup DDL."""
import os

from app import native_release, reference


def main():
    try:
        values = native_release.load_settings(os.environ)
        reference.verify(values['prepared_dir'])
    except Exception:
        raise SystemExit('Azure native startup refused') from None
    native_release.main()


if __name__ == '__main__':
    main()
