"""Exercise a new disposable backend container. Never target an existing service."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    args = parser.parse_args()
    cid = docker('run', '--rm', '-d', '--label', 'com.movelle.verification=smoke',
                 '-p', '127.0.0.1::8000', '-e', 'APP_ENV=development', '-e', 'MOVIELENS_PREPARED_DIR=/backend/reference',
                 '--mount', f'type=bind,source={args.prepared.resolve()},target=/backend/reference,readonly', args.image)
    if not re.fullmatch(r'[a-f0-9]{64}', cid): raise RuntimeError('Unexpected container identifier')
    try:
        port = docker('port', cid, '8000/tcp').rsplit(':', 1)[1]
        def call(path, method='GET', body=None, token=None):
            headers = {'Content-Type': 'application/json'}
            if token: headers['Authorization'] = 'Bearer ' + token
            request = Request(f'http://127.0.0.1:{port}{path}', method=method, headers=headers,
                              data=None if body is None else json.dumps(body).encode())
            try:
                with urlopen(request, timeout=5) as response: return response.status, json.load(response)
            except HTTPError as error: return error.code, json.load(error)
        for _ in range(60):
            try:
                if call('/health')[0] == 200: break
            except OSError: pass
            time.sleep(.25)
        else: raise RuntimeError('Disposable image did not start')
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
    finally:
        # Only the new container created above is stopped; --rm removes its synthetic DB.
        docker('stop', '-t', '5', cid)


if __name__ == '__main__':
    main()
