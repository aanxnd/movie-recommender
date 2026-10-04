"""Deadline-bounded database probes, isolated from application connections."""

import json
from pathlib import Path
import subprocess
import sys
from threading import Lock
import time


DATABASE_TIMEOUT = 3.0
CLEANUP_RESERVE = 0.5
_probe_lock = Lock()
_active_probe = None


def database_ready(engine, *, timeout: float = DATABASE_TIMEOUT) -> bool:
    """One disposable process at a time; kill stalled checkout/query/cleanup."""
    global _active_probe
    if not _probe_lock.acquire(blocking=False):
        return False
    deadline = time.monotonic() + timeout
    try:
        # Retain an unreaped process rather than starting competing probes.
        if _active_probe is not None:
            if _active_probe.poll() is None:
                return False
            _active_probe = None
        payload = json.dumps(engine.url.render_as_string(hide_password=False)).encode()
        # Fit the stdin write in the minimum pipe buffer, including on Windows.
        if len(payload) > 4096:
            return False
        _active_probe = subprocess.Popen(
            [sys.executable, "-m", "app.readiness"],
            cwd=Path(__file__).resolve().parents[1],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _active_probe.communicate(
            input=payload,
            timeout=max(0, deadline - time.monotonic() - CLEANUP_RESERVE),
        )
        return _active_probe.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
    finally:
        if _active_probe is not None:
            if _active_probe.poll() is None:
                try:
                    _active_probe.kill()
                    _active_probe.communicate(timeout=max(0, deadline - time.monotonic()))
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if _active_probe.poll() is not None:
                _active_probe = None
        _probe_lock.release()


def _worker_main() -> int:
    """Fresh connection, no shared pool; credentials arrive only through stdin."""
    from sqlalchemy import text
    from app.database import create_database_engine

    engine = None
    try:
        engine = create_database_engine(database_url=json.loads(sys.stdin.buffer.read()))
        with engine.connect() as connection:
            if connection.execute(text("SELECT 1")).scalar_one() != 1:
                return 1
        return 0
    except Exception:
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(_worker_main())
