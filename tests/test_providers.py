import io
import json
from urllib.error import HTTPError
import pytest
from app.providers import NoRedirect, ProviderClient, ProviderFailure


class Reply(io.BytesIO):
    pass


def test_provider_keys_are_only_headers_and_personal_key_is_additional():
    calls=[]
    def opener(request,**kw):
        calls.append(request)
        return Reply(json.dumps({'ok':True}).encode())
    client=ProviderClient('fixture-client','fixture-project',opener=opener)
    client.fetch('trakt','movies/tt0133093',{'extended':'full'})
    client.fetch('fanart','movies/tt0133093',{'source':'imdb'},personal_key='personal-fixture')
    assert calls[0].get_header('Trakt-api-key')=='fixture-client'
    assert calls[1].get_header('Api-key')=='fixture-project'
    assert calls[1].get_header('Client-key')=='personal-fixture'
    assert all(key not in request.full_url for request in calls for key in ['fixture-client','fixture-project','personal-fixture'])
    assert NoRedirect().redirect_request(None,None,None,None,None,None) is None


@pytest.mark.parametrize('status',[401,403,429])
def test_auth_and_quota_failures_do_not_retry_or_reveal_transport_details(status):
    calls=[];now=[1.]
    def failed(request,**kw):
        calls.append(1)
        raise HTTPError('https://provider.invalid/private',status,'confidential',{'Retry-After':'123'},None)
    client=ProviderClient('fixture',opener=failed,clock=lambda:now[0])
    with pytest.raises(ProviderFailure) as error: client.fetch('trakt','movies/1')
    assert str(error.value)=='Film provider unavailable'
    assert len(calls)==1
    now[0]+=100
    with pytest.raises(ProviderFailure):client.fetch('trakt','movies/1')
    assert len(calls)==1


def test_server_errors_retry_once_and_404_is_an_honest_miss():
    calls=[]
    def busy(request,**kw): calls.append(1);raise HTTPError(request.full_url,503,'private',{},None)
    client=ProviderClient('fixture',opener=busy,sleep=lambda _:None)
    with pytest.raises(ProviderFailure):client.fetch('trakt','movies/1')
    assert len(calls)==2
    def missing(*a,**kw):raise HTTPError('https://provider.invalid',404,'missing',{},None)
    assert ProviderClient('fixture',opener=missing).fetch('trakt','movies/1') is None


def test_response_size_and_unknown_provider_are_bounded():
    client=ProviderClient('fixture',opener=lambda *a,**kw:Reply(b'x'*512001))
    with pytest.raises(ProviderFailure):client.fetch('trakt','movies/1')
    with pytest.raises(ProviderFailure):client.fetch('other','movies/1')


def test_application_upstream_budget_also_applies_to_personal_keys():
    calls=[]
    def opener(*a,**kw): calls.append(1);return Reply(b'{}')
    client=ProviderClient('fixture','fixture',opener=opener)
    client.budget=2
    client.fetch('fanart','movies/tt0133093')
    client.fetch('fanart','movies/tt0133093',personal_key='one-fixture')
    with pytest.raises(ProviderFailure):client.fetch('fanart','movies/tt0133093',personal_key='another-fixture')
    assert len(calls)==2
