import pytest
from app import runtime


@pytest.mark.parametrize('configured,port',[(None,8000),('12345',12345)])
def test_bootstrap_precedes_single_worker_launch(monkeypatch,tmp_path,configured,port):
    calls=[]
    monkeypatch.delenv('PORT',raising=False)
    if configured: monkeypatch.setenv('PORT',configured)
    monkeypatch.setenv('MOVIELENS_PREPARED_DIR',str(tmp_path/'prepared'))
    monkeypatch.delenv('MOVIELENS_ARCHIVE_URL',raising=False)
    monkeypatch.delenv('MOVIELENS_ARCHIVE_SHA256',raising=False)
    monkeypatch.setattr(runtime,'ensure_prepared',lambda *args:calls.append(('bootstrap',args)))
    monkeypatch.setattr(runtime.uvicorn,'run',lambda *args,**kwargs:calls.append(('run',kwargs)))
    runtime.main()
    assert calls[0][0]=='bootstrap' and calls[0][1][1:]==(None,None)
    assert calls[1]==('run',{'host':'0.0.0.0','port':port,'workers':1,'reload':False})


@pytest.mark.parametrize('port',['0','65536','bad'])
def test_invalid_port_fails_before_bootstrap(monkeypatch,port):
    monkeypatch.setenv('PORT',port)
    monkeypatch.setattr(runtime,'ensure_prepared',lambda *args:pytest.fail('Unexpected bootstrap'))
    with pytest.raises(SystemExit,match='PORT'): runtime.main()


def test_failed_bootstrap_never_launches(monkeypatch):
    monkeypatch.delenv('PORT',raising=False)
    def fail(*args): raise runtime.BootstrapError('Safe bootstrap failure')
    monkeypatch.setattr(runtime,'ensure_prepared',fail)
    monkeypatch.setattr(runtime.uvicorn,'run',lambda *args,**kwargs:pytest.fail('Unexpected server'))
    with pytest.raises(SystemExit,match='Safe bootstrap'): runtime.main()
