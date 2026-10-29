"""Deadline-bounded database probes, isolated from application connections."""

import json
from pathlib import Path
import subprocess
import sys
from threading import Condition, Lock
import time


DATABASE_TIMEOUT = 3.0
CLEANUP_RESERVE = 0.5
_probe_lock = Lock()
_active_probe = None


class CachedReadiness:
    """One probe per cache interval; overlapping callers share the result."""
    def __init__(self, engine, *, success_ttl=30, failure_ttl=2):
        self.engine = engine
        self.success_ttl = success_ttl
        self.failure_ttl = failure_ttl
        self.condition = Condition()
        self.running = False
        self.checked_at = 0.0
        self.result = False

    def check(self):
        with self.condition:
            ttl = self.success_ttl if self.result else self.failure_ttl
            if self.checked_at and time.monotonic() - self.checked_at < ttl:
                return self.result
            if self.running:
                completed = self.condition.wait_for(lambda: not self.running, DATABASE_TIMEOUT + .5)
                return self.result if completed else False
            self.running = True
        result = False
        try:
            result = database_ready(self.engine)
            return result
        finally:
            with self.condition:
                self.result = result
                self.checked_at = time.monotonic()
                self.running = False
                self.condition.notify_all()


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
