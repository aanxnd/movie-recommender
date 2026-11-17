from types import SimpleNamespace

import pytest

from app import native_preflight as preflight


@pytest.mark.parametrize('failure', [None, 'config', 'reference', 'engine', 'schema', 'dispose'])
def test_release_preflight_is_read_only_generic_and_disposes(monkeypatch, capsys, failure):
    calls = []
    def step(name, value=None):
        calls.append(name)
        if name == failure: raise RuntimeError('DO_NOT_LOG_DATABASE_URL')
        return value
    engine = SimpleNamespace(dispose=lambda: step('dispose'))
    monkeypatch.setattr(preflight.native_release, 'load_settings', lambda _: step('config',
        {'prepared_dir': '/fixture', 'database_url': 'offline-fixture'}))
    monkeypatch.setattr(preflight.reference, 'verify', lambda _: step('reference'))
    monkeypatch.setattr(preflight.database, 'create_database_engine', lambda **_: step('engine', engine))
    monkeypatch.setattr(preflight, 'check_schema', lambda _: step('schema'))
    if failure:
        with pytest.raises(SystemExit, match='^Native release preflight refused$'): preflight.main()
    else:
        preflight.main()
        assert calls == ['config', 'reference', 'engine', 'schema', 'dispose']
    assert ('dispose' in calls) == (failure in {None, 'schema', 'dispose'})
    assert 'DO_NOT_LOG' not in str(capsys.readouterr())
