"""Offline preparation only; synthetic files/providers and no database connection."""
import hashlib
import json
from pathlib import Path
import tarfile
import shutil
import subprocess
import sys

import pytest

from deploy.oracle import entry, reference
from test_historical import artifacts
from test_native_release import config


@pytest.fixture
def prepared(artifacts, monkeypatch):
    output = artifacts
    # Synthetic fixture substitutes ONLY the code pin, never a runtime option.
    monkeypatch.setattr(reference, 'MANIFEST', hashlib.sha256((output / 'manifest.json').read_bytes()).hexdigest())
    return output


def test_reference_packaging_is_deterministic_complete_and_exclusive(prepared, tmp_path):
    first, second = tmp_path / 'one.tar.gz', tmp_path / 'two.tar.gz'
    reference.package(prepared, first)
    reference.package(prepared, second)
    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first) as archive:
        assert {m.name for m in archive} == {'ml-32m-v1/' + n for n in reference.FILES}
        for member in archive:
            assert member.isfile() and member.uid == member.gid == member.mtime == 0
            assert archive.extractfile(member).read() == (prepared / Path(member.name).name).read_bytes()
    with pytest.raises(FileExistsError):
        reference.package(prepared, first)


@pytest.mark.parametrize('change', ['manifest', 'array', 'license', 'extra', 'missing'])
def test_corrupt_or_incomplete_reference_never_packages(prepared, tmp_path, change):
    name = {'manifest': 'manifest.json', 'array': 'profile_ratings.npy', 'license': 'README.txt',
            'extra': 'unexpected', 'missing': 'catalog.json'}[change]
    if change == 'missing': (prepared / name).unlink()
    else: (prepared / name).write_bytes(b'corrupt')
    output = tmp_path / 'out.tar.gz'
    with pytest.raises(Exception): reference.package(prepared, output)
    assert not output.exists()


def test_small_data_cannot_pass_the_actual_production_manifest_pin(artifacts):
    with pytest.raises(ValueError, match='Pinned reference'):
        reference.verify(artifacts)


def test_reference_script_imports_in_the_flat_container_layout(artifacts, tmp_path):
    flat = tmp_path / 'container'
    shutil.copytree('app', flat / 'app', ignore=shutil.ignore_patterns('__pycache__'))
    script = flat / 'oracle-reference.py'
    shutil.copyfile('deploy/oracle/reference.py', script)
    result = subprocess.run([sys.executable, str(script), '--prepared', str(artifacts)],
                            cwd=flat, capture_output=True, text=True, timeout=30)
    assert result.returncode != 0  # Small cannot pass real production pin.
    assert result.stderr.strip() == 'Reference operation refused; incomplete output must not be used'


def test_copied_archive_is_verified_independently(prepared, tmp_path, monkeypatch):
    output = tmp_path / 'bad.tar.gz'
    reference.package(prepared, output)
    monkeypatch.setattr(reference, 'MANIFEST', '0' * 64)
    with pytest.raises(ValueError, match='checksum mismatch'):
        reference.verify_archive(output)


@pytest.fixture
def secrets(tmp_path):
    env, targets = config()
    for variable, filename in [('MOVELLE_NATIVE_DATABASE_URL', 'native_database_url'),
                               ('MOVELLE_NATIVE_PUBLISHABLE_KEY', 'native_publishable_key')]:
        (tmp_path / filename).write_text(env.pop(variable), encoding='utf-8')
    manifest = tmp_path / 'targets.json'
    manifest.write_text(json.dumps(targets))
    env['MOVELLE_NATIVE_TARGETS_FILE'] = str(manifest)
    return env, tmp_path


def test_file_secrets_preserve_the_existing_exact_native_contract(secrets):
    env, root = secrets
    values, config = entry.runtime_environment(env, root)
    assert config['project_url'] == 'https://' + 'a' * 20 + '.supabase.co'
    assert 'MOVELLE_NATIVE_DATABASE_URL' in values and 'MOVELLE_NATIVE_DATABASE_URL' not in env


@pytest.mark.parametrize('change', ['missing', 'directory', 'oversized', 'newline', 'ambient', 'origin', 'proxy', 'mode'])
def test_invalid_secret_or_release_config_refuses_before_any_connection(secrets, change):
    env, root = secrets
    file = root / 'native_database_url'
    if change == 'missing': file.unlink()
    elif change == 'directory': file.unlink(); file.mkdir()
    elif change == 'oversized': file.write_text('x' * 8193)
    elif change == 'newline': file.write_text('secret\nother-secret')
    elif change == 'ambient': env['MOVELLE_NATIVE_DATABASE_URL'] = 'secret'
    elif change == 'origin': env['CORS_ALLOWED_ORIGINS'] = '*'
    elif change == 'proxy': env['TRUSTED_PROXY_IPS'] = '*'
    elif change == 'mode': env['MOVELLE_NATIVE_MODE'] = 'legacy'
    with pytest.raises(Exception): entry.runtime_environment(env, root)


def test_image_context_excludes_everything_except_runtime_dependencies_and_entry():
    dockerfile = Path('deploy/oracle/Dockerfile').read_text()
    assert 'app.native_release' in dockerfile and 'USER 10001:10001' in dockerfile
    assert '--require-hashes --only-binary=:all:' in dockerfile
    assert 'COPY data' not in dockerfile and 'migrate' not in dockerfile
    ignored = Path('deploy/oracle/Dockerfile.dockerignore').read_text().splitlines()
    assert ignored[0] == '**' and '!requirements.txt' in ignored
    assert not any('secret' in item or 'targets' in item or 'data/' in item for item in ignored)


def test_entry_refuses_unknown_command_without_echoing_environment(monkeypatch, capsys):
    monkeypatch.setenv('MOVELLE_NATIVE_DATABASE_URL', 'DO_NOT_ECHO_SECRET')
    monkeypatch.setattr(entry.sys, 'argv', ['oracle-entry.py', 'migrate'])
    with pytest.raises(SystemExit, match='^Oracle native startup refused$'):
        entry.main()
    assert capsys.readouterr() == ('', '')
