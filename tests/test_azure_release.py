"""Synthetic trusted configuration only; no cloud, database or account calls."""
import json
from pathlib import Path

import pytest

from app import azure_release, native_release
from test_native_release import config


def test_azure_native_entry_checks_reference_before_starting(monkeypatch):
    calls = []
    monkeypatch.setattr(native_release, 'load_settings', lambda _: {'prepared_dir': '/fixture'})
    monkeypatch.setattr(azure_release.reference, 'verify', lambda path: calls.append(path))
    monkeypatch.setattr(native_release, 'main', lambda: calls.append('native'))
    azure_release.main()
    assert calls == ['/fixture', 'native']


@pytest.mark.parametrize('failure', ['config', 'reference'])
def test_azure_failure_is_generic_and_never_starts_a_server(monkeypatch, failure, capsys):
    def fail(*_): raise ValueError('DO_NOT_LOG_DATABASE_URL')
    monkeypatch.setattr(native_release, 'load_settings', fail if failure == 'config' else lambda _: {'prepared_dir': '/fixture'})
    monkeypatch.setattr(azure_release.reference, 'verify', fail)
    monkeypatch.setattr(native_release, 'main', lambda: pytest.fail('Server started'))
    with pytest.raises(SystemExit, match='^Azure native startup refused$'): azure_release.main()
    assert capsys.readouterr() == ('', '')


def test_environment_manifest_reuses_all_existing_target_guards(tmp_path):
    env, targets = config()
    env['MOVELLE_NATIVE_TARGETS_JSON'] = json.dumps(targets)
    assert native_release.load_settings(env) == native_release.settings(env, targets)
    env['MOVELLE_NATIVE_TARGETS_FILE'] = str(tmp_path / 'not-read')
    with pytest.raises(ValueError): native_release.load_settings(env)
    del env['MOVELLE_NATIVE_TARGETS_FILE']
    for raw in ['{}', '[]', '{"approved":true,"approved":false}', 'x' * 8193, 'null']:
        env['MOVELLE_NATIVE_TARGETS_JSON'] = raw
        with pytest.raises(ValueError): native_release.load_settings(env)


def test_release_image_carries_only_runtime_and_verified_immutable_reference():
    raw = Path('deploy/azure/Dockerfile').read_text()
    assert 'app.azure_release' in raw and 'USER 10001:10001' in raw
    assert '--require-hashes --only-binary=:all:' in raw
    assert 'FROM scratch AS reference' in raw and 'COPY --from=reference / /backend/data/reference/ml-32m-v1/' in raw
    assert 'RUN python -m app.reference' in raw and 'curl' not in raw
    assert 'migrate' not in raw and 'app.runtime' not in raw
    assert Path('deploy/azure/Dockerfile.dockerignore').read_text().startswith('**\n')
