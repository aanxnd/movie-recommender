import json
from pathlib import Path

import pytest

from deploy.oracle import render
from test_native_release import config


def targets():
    _, values = config()
    return {**values, 'api_origin': 'https://api.example'}


def test_rendering_is_offline_exact_origin_and_exclusive(tmp_path):
    file = tmp_path / 'reviewed.json'
    file.write_text(json.dumps(targets()))
    output = tmp_path / 'new'
    render.prepare(file, output)
    assert json.loads((output / 'targets.json').read_text()) == targets()
    proxy = (output / 'nginx.conf').read_text()
    assert 'server_name api.example;' in proxy and '@@' not in proxy
    assert 'return 308 https://api.example/;' in proxy  # No arbitrary redirects/query leakage.
    assert 'ssl_reject_handshake on;' in proxy and 'access_log off;' in proxy
    with pytest.raises(FileExistsError): render.prepare(file, output)


@pytest.mark.parametrize('value', ['http://api.example', 'https://api.example/',
    'https://api.example:443', 'https://user:secret@api.example', 'https://*.example',
    'https://api.example?token=secret', 'https://api.example;include /secret;',
    'https://localhost', 'https://127.0.0.1', 'https://10.0.0.1', 'https://[::1]'])
def test_unapproved_or_injectable_origins_are_refused(value):
    with pytest.raises(ValueError): render.render({**targets(), 'api_origin': value})


@pytest.mark.parametrize('change', [{'approved': False}, {'database_host': 'attacker.example'},
    {'database_name': '../secret'}, {'supabase_url': 'https://attacker.example'},
    {'api_origin': 'https://frontend.example'}])
def test_wrong_configuration_cannot_generate_a_proxy(change):
    with pytest.raises(ValueError): render.render({**targets(), **change})


def test_manifest_duplicate_keys_or_oversize_fail_before_output(tmp_path):
    file, output = tmp_path / 'targets.json', tmp_path / 'output'
    for raw in ['{"approved":false,"approved":true}', 'x' * 8193]:
        file.write_text(raw)
        with pytest.raises(ValueError): render.prepare(file, output)
        assert not output.exists()


def test_ip_literal_tls_requires_no_sni_and_still_binds_the_exact_http_host():
    # Public-address shape only; no connection or owner endpoint selection.
    proxy = render.render({**targets(), 'api_origin': 'https://8.8.8.8'})
    assert 'listen 8443 ssl default_server;' in proxy
    assert 'ssl_reject_handshake' not in proxy and '@@' not in proxy
    assert "if ($ssl_server_name != '') { return 444; }" in proxy
    assert "if ($http_host != '8.8.8.8') { return 444; }" in proxy
    dns = render.render(targets())
    assert 'ssl_reject_handshake on;' in dns
    assert '$ssl_server_name' not in dns


def test_compose_has_no_public_api_or_privileged_runtime_and_health_never_wakes_db():
    raw = Path('deploy/oracle/compose.yaml').read_text()
    api, proxy = raw.split('  proxy:', 1)
    assert 'ports:' not in api and '/ready' not in raw
    assert 'privileged:' not in raw and 'docker.sock' not in raw
    for section in [api, proxy]:
        assert 'read_only: true' in section and 'cap_drop: [ALL]' in section
        assert 'no-new-privileges:true' in section and 'pids_limit:' in section
        assert 'memswap_limit:' in section and 'max-size: 1m' in section
    assert 'create_host_path: false' in raw and 'on-failure:3' in raw
    assert 'native_database_url' in raw and 'MOVELLE_NATIVE_DATABASE_URL:' not in raw
