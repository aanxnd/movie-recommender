"""Execute only the actual workflow request helper; Azure subprocess is fictional."""
import ast
import json
import os
from pathlib import Path
import re
import stat
import textwrap
from types import SimpleNamespace

import pytest


@pytest.fixture
def request_helper(tmp_path):
    workflow = Path('.github/workflows/publish-image.yml').read_text(encoding='utf-8')
    blocks = re.findall(r"^          python - <<'PY'\n(.*?)^          PY$", workflow, re.M | re.S)
    functions = [node for block in blocks for node in ast.walk(ast.parse(textwrap.dedent(block)))
                 if isinstance(node, ast.FunctionDef) and node.name == 'request']
    assert len(functions) == 1
    calls = []
    response = SimpleNamespace(returncode=0, stdout='{"accepted":true}', stderr='')

    def run(args, **kwargs):
        # No child process or network call. Inspect the file while the helper runs.
        body = None
        if '--body' in args:
            argument = args[args.index('--body') + 1]
            assert argument == '@' + str(tmp_path / 'request.json')
            path = Path(argument[1:])
            body = json.loads(path.read_text(encoding='utf-8'))
            if os.name == 'posix':
                assert stat.S_IMODE(path.stat().st_mode) == 0o600
        calls.append((args, kwargs, body))
        return response

    namespace = dict(base='https://azure.invalid/resource', directory=str(tmp_path),
                     Path=Path, os=os, json=json, subprocess=SimpleNamespace(run=run))
    code = ast.Module(body=functions, type_ignores=[])
    exec(compile(code, '<workflow request helper>', 'exec'), namespace)
    return namespace['request'], calls, response


def test_patch_writes_private_json_before_invoking_cli_without_secret_arguments(request_helper, capsys):
    request, calls, _ = request_helper
    secret = 'DO_NOT_LOG_SECRET"\\\n\u00e9'
    body = {'properties': {'configuration': {'secrets': [{'name': 'fixture', 'value': secret}]}}}
    assert request('patch', body=body) == {'accepted': True}
    assert len(calls) == 1
    args, options, actual = calls[0]
    assert args[:5] == ['az', 'rest', '--method', 'patch', '--url']
    assert args[5] == 'https://azure.invalid/resource?api-version=2025-07-01'
    assert options == {'capture_output': True, 'text': True}
    assert actual == body and secret not in ' '.join(args)
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize('method', ['get', 'post'])
def test_bodyless_inspection_does_not_create_or_send_body(request_helper, method):
    request, calls, _ = request_helper
    request(method)
    assert len(calls) == 1 and '--body' not in calls[0][0] and calls[0][2] is None


def test_cli_failure_is_not_retried_or_printed(request_helper, capsys):
    request, calls, response = request_helper
    response.returncode = 1
    response.stderr = 'ERROR: DO_NOT_LOG_SECRET_OR_AZURE_BODY'
    with pytest.raises(RuntimeError, match='^Azure request failed$'):
        request('patch', body={'fixture': 'DO_NOT_LOG_SECRET'})
    assert len(calls) == 1 and capsys.readouterr() == ('', '')
