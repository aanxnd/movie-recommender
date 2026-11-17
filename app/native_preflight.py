"""Read-only release check before an approved Azure update; never migrate."""
import os

from app import database, native_release, reference
from app.migrations import check_schema


def main():
    engine = None
    try:
        values = native_release.load_settings(os.environ)
        reference.verify(values['prepared_dir'])
        engine = database.create_database_engine(database_url=values['database_url'])
        check_schema(engine)
    except Exception:
        raise SystemExit('Native release preflight refused') from None
    finally:
        if engine is not None:
            try: engine.dispose()
            except Exception: raise SystemExit('Native release preflight refused') from None
    print('Native release reference and schema verified; no migration performed')


if __name__ == '__main__':
    main()
