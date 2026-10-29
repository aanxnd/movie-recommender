"""Exercise startup failures without a daemon, network, or production credentials."""
import io
import json
import subprocess
import sys
from urllib.error import HTTPError, URLError

import pytest

from scripts import smoke_container as smoke


CID = 'a' * 64
IMAGE = 'ghcr.io/aanxnd/movie-recommender@sha256:' + 'b' * 64


@pytest.fixture
def runner(monkeypatch, tmp_path):
    commands, housekeeping = [], []
    state = {'Running': True, 'ExitCode': 0}

    def docker(*args):
        commands.append(args)
        return {'run': CID, 'port': '127.0.0.1:12345', 'inspect': json.dumps(state), 'exec': 'ok'}[args[0]]

    def run(args, **kwargs):
        housekeeping.append(args)
        return subprocess.CompletedProcess(args, 0, '', '')

    def urlopen(request, **kwargs):
        path = request.full_url.split(':12345')[1]
        body, status = {}, 200
        if path == '/users':
            body, status = {'id': 1, 'token': 'test-token'}, 201
        elif path == '/users/1/ratings':
            raise HTTPError(request.full_url, 401, 'Unauthorized', {}, io.BytesIO(b'{}'))
        elif path == '/users/1/ratings/details':
            body = {'items': [{'rating': 3.25, 'available': True}]}
        response = io.BytesIO(json.dumps(body).encode())
        response.status = status
        return response

    monkeypatch.setattr(sys, 'argv', ['smoke_container.py', '--image', IMAGE, '--prepared', str(tmp_path)])
    monkeypatch.setattr(smoke, 'docker', docker)
    monkeypatch.setattr(smoke.subprocess, 'run', run)
    monkeypatch.setattr(smoke, 'urlopen', urlopen)
    monkeypatch.setattr(smoke.time, 'sleep', lambda _: None)
    return commands, housekeeping, state


def test_exact_image_smoke_keeps_nonroot_readonly_checks_and_cleans_up(runner, capsys):
    commands, housekeeping, _ = runner
    smoke.main()
    launch = commands[0]
    assert launch[0] == 'run' and launch[-1] == IMAGE
    assert '--rm' not in launch and '--user' not in launch
    assert 'APP_ENV=development' in launch
    assert any('target=/backend/reference,readonly' in arg for arg in launch)
    assert any(command[0] == 'exec' and 'os.getuid()==10001' in command[-1] for command in commands)
    assert housekeeping == [['docker', 'rm', '--force', CID]]
    assert '7 checks passed' in capsys.readouterr().out


@pytest.mark.parametrize('already_removed', [False, True])
def test_early_exit_reports_logs_and_cleanup_preserves_failure(runner, monkeypatch, capsys, already_removed):
    commands, housekeeping, state = runner
    state.update(Running=False, ExitCode=1)

    def run(args, **kwargs):
        housekeeping.append(args)
        if args[1] == 'logs':
            return subprocess.CompletedProcess(args, 0, 'PermissionError: reference data inaccessible', '')
        if args[1] == 'rm' and already_removed:
            return subprocess.CompletedProcess(args, 1, '', 'Error: No such container: ' + CID)
        return subprocess.CompletedProcess(args, 0, '{}', '')

    monkeypatch.setattr(smoke.subprocess, 'run', run)
    monkeypatch.setattr(smoke, 'urlopen', lambda *a, **k: pytest.fail('Exited container must fail immediately'))
    with pytest.raises(RuntimeError, match='exited before startup .exit code 1'):
        smoke.main()
    assert sum(command[0] == 'inspect' for command in commands) == 1
    assert housekeeping[-1] == ['docker', 'rm', '--force', CID]
    assert 'PermissionError' in capsys.readouterr().err


def test_running_container_timeout_still_fails_and_cleans_up(runner, monkeypatch):
    commands, housekeeping, _ = runner

    def unavailable(*args, **kwargs):
        raise URLError('connection refused')

    monkeypatch.setattr(smoke, 'urlopen', unavailable)
    with pytest.raises(RuntimeError, match='Disposable image did not start'):
        smoke.main()
    assert sum(command[0] == 'inspect' for command in commands) == 60
    assert housekeeping[-1] == ['docker', 'rm', '--force', CID]


def test_delayed_startup_can_recover(monkeypatch):
    monkeypatch.setattr(smoke, 'docker', lambda *args: '{"Running": true}')
    monkeypatch.setattr(smoke.time, 'sleep', lambda _: None)
    attempts = []

    def call(path):
        attempts.append(path)
        if len(attempts) < 3:
            raise URLError('connection refused')
        return 200, {}

    smoke.wait_for_health(CID, call)
    assert attempts == ['/health'] * 3


def test_failed_readiness_still_blocks_image(runner, monkeypatch):
    _, housekeeping, _ = runner

    def not_ready(request, **kwargs):
        raise HTTPError(request.full_url, 503, 'Not ready', {}, io.BytesIO(b'{}'))

    monkeypatch.setattr(smoke, 'wait_for_health', lambda *args: None)
    monkeypatch.setattr(smoke, 'urlopen', not_ready)
    with pytest.raises(AssertionError):
        smoke.main()
    assert housekeeping[-1] == ['docker', 'rm', '--force', CID]


@pytest.mark.parametrize('failure', [OSError('daemon unavailable'), subprocess.TimeoutExpired('docker', 5)])
def test_diagnostics_and_cleanup_errors_do_not_mask_startup_failure(runner, monkeypatch, failure):
    runner[2].update(Running=False, ExitCode=1)

    def unavailable(*args, **kwargs):
        raise failure

    monkeypatch.setattr(smoke.subprocess, 'run', unavailable)
    with pytest.raises(RuntimeError, match='exited before startup'):
        smoke.main()


def test_cleanup_other_daemon_error_is_visible(monkeypatch, capsys):
    monkeypatch.setattr(smoke.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, 1, '', 'denied'))
    smoke.cleanup(CID)
    assert 'Warning: could not remove' in capsys.readouterr().err
