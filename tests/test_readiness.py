"""Real disposable processes demonstrate that stalled probes cannot accumulate."""

from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys
import textwrap
from types import SimpleNamespace
import time

import pytest
from sqlalchemy.engine import make_url

from app import database, readiness


@pytest.mark.parametrize('phase', ['checkout', 'query', 'cleanup'])
def test_stalled_readiness_is_killed_and_reaped(tmp_path, monkeypatch, phase):
    entered = tmp_path / 'entered'
    script = textwrap.dedent(f'''
        from pathlib import Path
        import time
        from app import database, readiness
        def stall(phase):
            if phase == {phase!r}:
                Path({str(entered)!r}).write_text(phase)
                time.sleep(60)
        class Connection:
            def __enter__(self):
                stall('checkout')
                return self
            def __exit__(self, *args): pass
            def execute(self, statement):
                stall('query')
                return self
            def scalar_one(self): return 1
        class Engine:
            def connect(self): return Connection()
            def dispose(self): stall('cleanup')
        database.create_database_engine = lambda **kwargs: Engine()
        raise SystemExit(readiness._worker_main())
    ''')
    original_popen = subprocess.Popen
    processes = []
    def start(args, **kwargs):
        process = original_popen([sys.executable, '-c', script], **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(readiness.subprocess, 'Popen', start)
    engine = SimpleNamespace(url=make_url('postgresql://localhost/disposable'))
    for _ in range(2):
        entered.unlink(missing_ok=True)
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=1) as pool:
            active = pool.submit(readiness.database_ready, engine, timeout=2.0)
            deadline = started + 1.5
            while not entered.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            assert entered.read_text() == phase
            # A simultaneous check rejects immediately rather than spawning/queuing.
            before = len(processes)
            assert readiness.database_ready(engine, timeout=2.0) is False
            assert len(processes) == before
            assert active.result(timeout=3) is False
        assert time.monotonic() - started < 3
        assert processes[-1].poll() is not None
        assert readiness._active_probe is None
        assert processes[-1].stdin.closed
    assert len(processes) == 2


def test_readiness_success_uses_fresh_connection_not_application_pool(tmp_path, monkeypatch):
    engine = database.create_database_engine(tmp_path / 'ready.db')
    try:
        monkeypatch.setattr(engine, 'connect', lambda: pytest.fail('Application pool used'))
        assert readiness.database_ready(engine) is True
    finally:
        engine.dispose()


def test_readiness_worker_error_is_sanitized(tmp_path, capsys):
    engine = SimpleNamespace(url=make_url(f'sqlite:///{(tmp_path / "missing/ready.db").as_posix()}?unknown=1'))
    # An invalid filesystem target is a deterministic worker-side failure.
    target = tmp_path / 'missing'
    target.write_text('not a directory')
    assert readiness.database_ready(engine) is False
    assert not capsys.readouterr().err


def test_readiness_launch_failure_releases_guard(monkeypatch):
    def fail(*args, **kwargs): raise OSError('private launch details')
    monkeypatch.setattr(readiness.subprocess, 'Popen', fail)
    engine = SimpleNamespace(url=make_url('sqlite:///:memory:'))
    assert readiness.database_ready(engine) is False
    assert readiness.database_ready(engine) is False
    assert readiness._active_probe is None


def test_unreaped_probe_prevents_additional_processes(monkeypatch):
    class Process:
        def poll(self): return None
        def communicate(self, **kwargs): raise subprocess.TimeoutExpired('probe', 0)
        def kill(self): pass
    calls = []
    def start(*args, **kwargs):
        calls.append(True)
        return Process()
    monkeypatch.setattr(readiness, '_active_probe', None)
    monkeypatch.setattr(readiness.subprocess, 'Popen', start)
    engine = SimpleNamespace(url=make_url('sqlite:///:memory:'))
    for _ in range(5):
        assert readiness.database_ready(engine, timeout=.1) is False
    assert len(calls) == 1
    assert readiness._active_probe is not None
