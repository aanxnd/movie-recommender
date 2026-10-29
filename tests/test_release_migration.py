"""Execute the real release shell script with fake tools; never connect to a DB."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


SCRIPT = Path('scripts/migrate_release.sh').read_text()
IMAGE = 'ghcr.io/aanxnd/movie-recommender@sha256:' + 'a' * 64
# Synthetic canary only. Metacharacters must stay data and never enter argv/logs.
CANARY = 'postgresql://fixture:canary-$(false);@db.invalid/disposable?sslmode=require'
TOOLS = r'''
docker() {
  printf '%q ' "$@" >> "$TRACE"
  printf '\n' >> "$TRACE"
  printf '%s\n' "$DATABASE_URL"
  printf '%s\n' "$DATABASE_URL" >&2
  case "$1" in
    pull) return "${PULL_STATUS:-0}" ;;
    run) return "${RUN_STATUS:-0}" ;;
    rm) return 0 ;;
    *) return 99 ;;
  esac
}
timeout() {
  printf 'timeout %s %s %s\n' "$1" "$2" "$3" >> "$TRACE"
  if [[ ${TIMEOUT_STATUS:-0} != 0 ]]; then return "$TIMEOUT_STATUS"; fi
  shift 3
  "$@"
}
'''


@pytest.fixture
def run_script(tmp_path):
    bash = shutil.which('bash')
    if bash is None and os.name == 'nt':
        candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git/bin/bash.exe'
        if candidate.is_file(): bash = str(candidate)
    if bash is None:
        pytest.skip('Bash required for release-script behavioral tests')
    trace = tmp_path / 'tools.txt'
    def run(**overrides):
        # Supply a minimal environment: never inherit application/cloud credentials.
        env = {name: os.environ[name] for name in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP') if name in os.environ}
        env.update(IMAGE=IMAGE, DATABASE_URL=CANARY, APP_ENV='production',
                   CORS_ALLOWED_ORIGINS='https://frontend.example', TRACE=trace.as_posix())
        env.update(overrides)
        trace.unlink(missing_ok=True)
        result = subprocess.run([bash, '-s'], input=TOOLS + '\n' + SCRIPT, text=True,
                                capture_output=True, env=env, timeout=15)
        calls = trace.read_text() if trace.exists() else ''
        assert CANARY not in result.stdout + result.stderr + calls
        return result, calls
    return run


def test_migration_runs_only_the_digest_with_secret_names_and_cleans_up(run_script):
    result, calls = run_script()
    assert result.returncode == 0
    assert 'migration succeeded' in result.stdout
    lines = calls.splitlines()
    assert lines[0] == 'pull ' + IMAGE + ' '
    assert lines[1] == 'timeout --signal=TERM --kill-after=15s 300s'
    assert lines[2].startswith('run --rm --name movelle-migration-')
    assert IMAGE in lines[2]
    for flag in ('--pull=never', '--read-only', '--log-driver=none', '--cap-drop=ALL', '--security-opt=no-new-privileges'):
        assert flag in lines[2]
    assert '--env DATABASE_URL --env APP_ENV --env CORS_ALLOWED_ORIGINS' in lines[2]
    assert '--entrypoint /bin/sh' in lines[2]
    assert 'from app.config import validate' in lines[2]
    assert 'from app.main import cors_origins' in lines[2]
    assert '/usr/local/bin/movelle-migrate' in lines[2]
    assert '--volume' not in calls and '--mount' not in calls and '--privileged' not in calls
    assert lines[-1].startswith('rm --force movelle-migration-')


@pytest.mark.parametrize('overrides', [
    {'DATABASE_URL': ''}, {'APP_ENV': 'development'}, {'APP_ENV': ''},
    {'CORS_ALLOWED_ORIGINS': ''}, {'IMAGE': ''},
    {'IMAGE': 'ghcr.io/aanxnd/movie-recommender:latest'},
    {'IMAGE': 'ghcr.io/other/project@sha256:' + 'a' * 64},
    {'IMAGE': IMAGE + '; false'},
])
def test_missing_configuration_or_mutable_image_fails_before_docker(run_script, overrides):
    result, calls = run_script(**overrides)
    assert result.returncode != 0
    assert 'deployment blocked' in result.stdout
    assert calls == ''


def test_failed_pull_never_starts_migration(run_script):
    result, calls = run_script(PULL_STATUS='1')
    assert result.returncode != 0
    assert 'Cannot pull' in result.stdout
    assert 'run --rm' not in calls


@pytest.mark.parametrize('status', ['1', '125', '137'])
def test_container_validation_or_migration_failure_blocks_deploy_and_cleans_up(run_script, status):
    result, calls = run_script(RUN_STATUS=status)
    assert result.returncode != 0
    assert 'failed or timed out' in result.stdout
    assert 'migration succeeded' not in result.stdout
    assert calls.splitlines()[-1].startswith('rm --force ')


def test_timeout_fails_closed_and_cleans_up_without_logging_credentials(run_script):
    result, calls = run_script(TIMEOUT_STATUS='124')
    assert result.returncode != 0
    assert 'failed or timed out' in result.stdout
    assert calls.splitlines()[-1].startswith('rm --force ')
