"""Offline standard policy, using real local JWT signatures and mocked Auth responses."""
import json
import logging
from urllib.error import HTTPError
from uuid import uuid4

import pytest

from app import supabase_policy as policy
from test_supabase_claims import evidence
from test_supabase_jwt import ORIGIN


@pytest.fixture
def account(evidence, monkeypatch):
    e = evidence
    client = policy.SupabaseAccessPolicy(project_url=ORIGIN, audience="authenticated",
                                         publishable_key="sb_publishable_offline")
    client._verifier = e.verifier
    user = dict(id=str(e.subject), aud="authenticated", role="authenticated", is_anonymous=False,
                email="local@example.invalid", email_confirmed_at="2026-01-01T00:00:00Z", factors=[])
    calls = []
    def read(url, key, token):
        assert url == ORIGIN + "/auth/v1/user" and key == "sb_publishable_offline"
        assert token.count(".") == 2
        calls.append(token)
        return json.dumps(user).encode()
    monkeypatch.setattr(policy, "_read_user", read)
    return e, client, user, calls


@pytest.mark.parametrize("aal", ["aal1", "aal2"])
def test_native_confirmation_and_standard_token_lifetime(account, aal):
    e, client, user, calls = account
    token = e.sign({"aal": aal})
    # No session-row lookup or logout status is needed. An unexpired token can
    # remain usable after logout if the provider still accepts it.
    assert client.check(token).session_id == e.session_id
    assert client.check(token).subject == e.subject and len(calls) == 2
    user["app_metadata"] = {"admin_confirmed": True}
    assert client.check(token).aal == aal  # Native confirmation is the approved trust boundary.


@pytest.mark.parametrize("status,aal,allowed", [("verified", "aal1", False), ("verified", "aal2", True),
                                                ("unverified", "aal1", True)])
def test_enrolled_factor_cannot_be_bypassed_with_password(account, status, aal, allowed):
    e, client, user, _ = account
    user["factors"] = [dict(id=str(uuid4()), factor_type="totp", status=status)]
    if allowed:
        assert client.check(e.sign({"aal": aal})).aal == aal
    else:
        with pytest.raises(policy.AccessDenied): client.check(e.sign({"aal": aal}))


@pytest.mark.parametrize("change", [
    {"id": str(uuid4())}, {"email": None}, {"email": "@bad"}, {"email_confirmed_at": None},
    {"email_confirmed_at": "2026-01-01"}, {"email_confirmed_at": "2999-01-01T00:00:00Z"},
    {"is_anonymous": True}, {"is_anonymous": 0}, {"role": "service_role"}, {"aud": "other"},
    {"deleted_at": "2026-01-01T00:00:00Z"}, {"banned_until": "2999-01-01T00:00:00Z"},
    {"factors": {}}, {"factors": [None]}, {"factors": [{"id": str(uuid4()), "status": "verified"}]},
])
def test_rejected_provider_evidence(account, change):
    e, client, user, _ = account
    user.update(change)
    with pytest.raises(policy.AccessDenied): client.check(e.sign())


def test_metadata_and_signed_email_cannot_replace_confirmation(account):
    e, client, user, _ = account
    del user["email_confirmed_at"]
    user.update(confirmed_at="2026-01-01T00:00:00Z", user_metadata={"email_verified": True})
    with pytest.raises(policy.AccessDenied): client.check(e.sign({"email_verified": True}))


@pytest.mark.parametrize("change", [{"exp": 1}, {"aal": "aal3"}, {"sub": str(uuid4())}])
def test_invalid_or_substituted_token(account, change):
    e, client, _, _ = account
    with pytest.raises(policy.AccessDenied): client.check(e.sign(change))


@pytest.mark.parametrize("failure", [TimeoutError("private"), HTTPError("private", 429, "private", {}, None),
                                    HTTPError("private", 500, "private", {}, None)])
def test_outage_has_no_cached_success_or_fallback(account, monkeypatch, failure, caplog):
    e, client, user, _ = account
    token = e.sign()
    client.check(token)
    def broken(*_): raise failure
    monkeypatch.setattr(policy, "_read_user", broken)
    with caplog.at_level(logging.DEBUG), pytest.raises(policy.AccessUnavailable) as error:
        client.check(token)
    assert str(error.value) == "Authentication evidence unavailable"
    assert not any(secret in str(error.value) + caplog.text for secret in (token, str(e.subject), user["email"], "private"))


@pytest.mark.parametrize("body", [b"invalid", b'[]', b'{"id":"a","id":"b"}', b'{"factors":NaN}'])
def test_malformed_provider_data_fails_closed(account, monkeypatch, body):
    e, client, _, _ = account
    monkeypatch.setattr(policy, "_read_user", lambda *_: body)
    with pytest.raises((policy.AccessDenied, policy.AccessUnavailable)): client.check(e.sign())


@pytest.mark.parametrize("status", [401, 403, 404])
def test_provider_rejection(account, monkeypatch, status):
    e, client, _, _ = account
    def rejected(*_): raise HTTPError("private", status, "private", {}, None)
    monkeypatch.setattr(policy, "_read_user", rejected)
    with pytest.raises(policy.AccessDenied, match="^Authentication evidence rejected$"): client.check(e.sign())


@pytest.mark.parametrize("factors", [None, []])
def test_provider_omits_empty_factors(account, factors):
    e, client, user, _ = account
    user["factors"] = factors
    assert client.check(e.sign()).aal == "aal1"
    del user["factors"]
    assert client.check(e.sign()).aal == "aal1"


def test_address_change_requires_native_confirmation_again(account):
    e, client, user, _ = account
    client.check(e.sign())
    user.update(email="new@example.invalid", email_confirmed_at=None)
    with pytest.raises(policy.AccessDenied): client.check(e.sign())


def test_token_expiring_during_provider_read_is_rejected(account, monkeypatch):
    e, client, _, _ = account
    class Later(policy.datetime):
        @classmethod
        def now(cls, tz): return cls.fromtimestamp(e.now + 1000, tz)
    monkeypatch.setattr(policy, "datetime", Later)
    with pytest.raises(policy.AccessDenied): client.check(e.sign())


@pytest.mark.parametrize("factor", [{"id": "bad"}, {"id": str(uuid4()), "status": "verified", "factor_type": "phone"},
                                    {"id": str(uuid4()), "status": [], "factor_type": "totp"}])
def test_malformed_or_unsupported_factors_never_downgrade(account, factor):
    e, client, user, _ = account
    user["factors"] = [factor]
    with pytest.raises((policy.AccessDenied, policy.AccessUnavailable)): client.check(e.sign())
