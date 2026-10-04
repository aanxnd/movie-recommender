"""Provider-neutral production entrypoint: opt-in bootstrap, then one ASGI worker."""

import os
from pathlib import Path

import uvicorn

from app.bootstrap import BootstrapError, ensure_prepared
from app.data import DEFAULT_DATA_DIR


def main() -> None:
    try:
        port = int(os.environ.get("PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise SystemExit("PORT must be an integer between 1 and 65535") from None
    destination = Path(os.environ.get("MOVIELENS_PREPARED_DIR", str(DEFAULT_DATA_DIR / "prepared/ml-32m-v1")))
    try:
        ensure_prepared(destination, os.environ.get("MOVIELENS_ARCHIVE_URL"), os.environ.get("MOVIELENS_ARCHIVE_SHA256"))
    except BootstrapError as error:
        raise SystemExit(str(error)) from None
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, workers=1, reload=False)


if __name__ == "__main__":
    main()
