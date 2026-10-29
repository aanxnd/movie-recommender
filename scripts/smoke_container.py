"""Exercise a new disposable backend container. Never target an existing service."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def diagnostics(cid):
    # The disposable smoke container receives no production secrets. Inspect
    # state only (never its environment) and retain bounded startup logs.
    for command in (['inspect', '--format', '{{json .State}}'], ['logs', '--tail', '50']):
        try:
            result = subprocess.run(['docker', *command, cid], capture_output=True, text=True, timeout=5)
            print(f'Smoke container {command[0]}: {(result.stdout + result.stderr)[-8000:]}', file=sys.stderr)
        except (OSError, subprocess.TimeoutExpired):
            print(f'Smoke container {command[0]} unavailable', file=sys.stderr)


def cleanup(cid):
    # Only remove the new container's validated ID. An already-removed
    # container is harmless; cleanup must not replace the original failure.
    try:
        result = subprocess.run(['docker', 'rm', '--force', cid], capture_output=True, text=True, timeout=10)
        if result.returncode and 'No such container' not in result.stderr:
            print('Warning: could not remove disposable smoke container', file=sys.stderr)
    except (OSError, subprocess.TimeoutExpired):
        print('Warning: disposable smoke container cleanup unavailable', file=sys.stderr)


def wait_for_health(cid, call):
    for _ in range(60):
        state = json.loads(docker('inspect', '--format', '{{json .State}}', cid))
        if not state['Running']:
            raise RuntimeError(f"Disposable image exited before startup (exit code {state.get('ExitCode')})")
        try:
            if call('/health')[0] == 200:
                return
        except OSError:
            pass
        time.sleep(.25)
    raise RuntimeError('Disposable image did not start')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    args = parser.parse_args()
    # Retain exited containers until diagnostics have been collected.
    cid = docker('run', '-d', '--label', 'com.movelle.verification=smoke',
                 '-p', '127.0.0.1::8000', '-e', 'APP_ENV=development', '-e', 'MOVIELENS_PREPARED_DIR=/backend/reference',
                 '--mount', f'type=bind,source={args.prepared.resolve()},target=/backend/reference,readonly', args.image)
    if not re.fullmatch(r'[a-f0-9]{64}', cid): raise RuntimeError('Unexpected container identifier')
    try:
        binding = docker('port', cid, '8000/tcp')
        if not re.fullmatch(r'127\.0\.0\.1:\d+', binding):
            raise RuntimeError('Disposable image has no loopback port binding')
        port = binding.rsplit(':', 1)[1]
        def call(path, method='GET', body=None, token=None):
            headers = {'Content-Type': 'application/json'}
            if token: headers['Authorization'] = 'Bearer ' + token
            request = Request(f'http://127.0.0.1:{port}{path}', method=method, headers=headers,
                              data=None if body is None else json.dumps(body).encode())
            try:
                with urlopen(request, timeout=5) as response: return response.status, json.load(response)
            except HTTPError as error: return error.code, json.load(error)
        wait_for_health(cid, call)
        assert call('/ready')[0] == 200
        status, owner = call('/users', 'POST')
        assert status == 201
        assert call(f"/users/{owner['id']}/ratings")[0] == 401
        assert call(f"/users/{owner['id']}/ratings/1", 'PUT', {'rating': 3.25}, owner['token'])[0] == 200
        page = call(f"/users/{owner['id']}/ratings/details", token=owner['token'])[1]
        assert page['items'][0]['rating'] == 3.25 and page['items'][0]['available']
        assert call(f"/users/{owner['id']}/recommendations", token=owner['token'])[0] == 200
        assert docker('exec', cid, 'python', '-c', "import os,importlib.util;assert os.getuid()==10001;assert importlib.util.find_spec('pytest') is None;assert importlib.util.find_spec('httpx') is None;print('ok')") == 'ok'
        print('Container smoke: 7 checks passed (readiness, creation, ownership, write, metadata, recommendations, runtime footprint)')
    except Exception:
        diagnostics(cid)
        raise
    finally:
        cleanup(cid)


if __name__ == '__main__':
    main()
