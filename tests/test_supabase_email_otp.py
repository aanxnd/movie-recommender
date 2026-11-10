"""Offline native-provider redemption tests; no messages, hosted accounts or ledger."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import json
import traceback
from types import SimpleNamespace
from urllib.error import HTTPError
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app import supabase_email_otp as auth
from test_supabase_claims import evidence as jwt_evidence
from test_supabase_jwt import ORIGIN


@pytest.fixture
def env(jwt_evidence, monkeypatch):
    e = jwt_evidence
    now = datetime.fromtimestamp(e.now, timezone.utc)
    s = SimpleNamespace(e=e, now=now, code="123456", calls=[], error=None, raw=None, response_change={}, after_change={})
    s.original = e.sign()
    s.user = dict(id=str(e.subject), aud="authenticated", role="authenticated", is_anonymous=False,
                  email="current@example.invalid", email_confirmed_at=None)
    s.confirmed = {**s.user, "email_confirmed_at": now.isoformat()}
    s.result_token = e.sign({"iat": e.now, "session_id": str(uuid4()), "amr": [{"method": "otp", "timestamp": e.now}]})
    s.response = dict(access_token=s.result_token, token_type="bearer", refresh_token="synthetic-unused-refresh", user=s.confirmed)
    def read(url, key, token):
        assert url == ORIGIN + "/auth/v1/user" and key == "sb_publishable_test"
        s.calls.append("before" if token == s.original else "after")
        return json.dumps(s.user if token == s.original else {**s.confirmed, **s.after_change}).encode()
    def post(url, key, email, code):
        assert url == ORIGIN + "/auth/v1/verify" and key == "sb_publishable_test"
        assert email == s.user["email"] and code == "123456"
        s.calls.append("verify")
        if s.error: raise s.error
        return s.raw if s.raw is not None else json.dumps({**s.response, **s.response_change}).encode()
    def configured(project_url, *, audience):
        assert project_url == ORIGIN and audience == "authenticated"
        return e.verifier
    monkeypatch.setattr(auth, "SupabaseTokenVerifier", configured)
    monkeypatch.setattr(auth, "_read_user", read)
    monkeypatch.setattr(auth, "_post_verify", post)
    monkeypatch.setattr(auth, "_now", lambda: s.now)
    s.verifier = auth.SupabaseEmailOtpVerifier(project_url=ORIGIN, audience="authenticated", publishable_key="sb_publishable_test")
    assert not s.calls and not e.calls
    return s


def test_native_completion_of_unverified_account_preserves_binding(env):
    result = env.verifier.redeem(env.original, "123456")
    assert result.subject == env.e.subject and result.email == env.user["email"]
    assert result.issuer == ORIGIN + "/auth/v1" and result.confirmed_at == env.now
    assert env.calls == ["before", "verify", "after"]
    assert type(result) is auth.EmailOtpRedemption
    assert not hasattr(result, "access_token") and not hasattr(result, "refresh_token")
    assert env.user["email"] not in repr(result) and str(env.e.subject) not in repr(result)
    with pytest.raises(FrozenInstanceError): result.email = "forged@example.invalid"


def test_confirmation_marker_cannot_make_an_invalid_otp_valid(env):
    env.user.update(email_confirmed_at=(env.now-timedelta(days=30)).isoformat(),
                    user_metadata={"email_verified": True})
    env.error = HTTPError("redacted", 403, "invalid-or-expired", {}, None)
    with pytest.raises(auth.EmailOtpDenied): env.verifier.redeem(env.original, "123456")
    assert env.calls == ["before", "verify"]


def test_valid_native_code_preserves_existing_confirmation_marker(env):
    env.user["email_confirmed_at"] = (env.now-timedelta(days=30)).isoformat()
    env.confirmed["email_confirmed_at"] = env.user["email_confirmed_at"]
    assert type(env.verifier.redeem(env.original, "123456")) is auth.EmailOtpRedemption


@pytest.mark.parametrize("code", [None, True, 123456, "", "12345", "1234567", "１２３４５６", " 123456", "12345x"])
def test_invalid_challenge_input_never_contacts_provider(env, code):
    with pytest.raises(auth.EmailOtpDenied): env.verifier.redeem(env.original, code)
    assert env.calls == [] and env.e.calls == []


@pytest.mark.parametrize("field,value", [("id", str(uuid4())), ("aud", "other"), ("role", "service_role"),
    ("email", ""), ("email_confirmed_at", None), ("is_anonymous", True)])
def test_invalid_returned_user_evidence(env, field, value):
    env.response_change["user"] = {**env.confirmed, field: value}
    with pytest.raises(auth.EmailOtpDenied): env.verifier.redeem(env.original, "123456")


@pytest.mark.parametrize("claims", [{"sub": str(uuid4())}, {"exp": 1}, {"iss": "other"}, {"aud": "other"},
    {"iat": 1, "amr": [{"method": "otp", "timestamp": 1}]}, {"amr": []},
    {"amr": [{"method": "password", "timestamp": 1}]}])
def test_cross_account_expired_stale_or_non_otp_jwt_rejected(env, claims):
    env.response_change["access_token"] = env.e.sign({"iat": env.e.now, "session_id": str(uuid4()),
        "amr": [{"method": "otp", "timestamp": env.e.now}], **claims})
    with pytest.raises(auth.EmailOtpDenied): env.verifier.redeem(env.original, "123456")


def test_incorrect_signature_cannot_supply_completion(env):
    env.response_change["access_token"] = env.e.sign(key=ec.generate_private_key(ec.SECP256R1()))
    with pytest.raises(auth.EmailOtpDenied): env.verifier.redeem(env.original, "123456")


def test_old_session_or_caller_supplied_claims_cannot_be_completion(env):
    env.response_change["access_token"] = env.original
    with pytest.raises(auth.EmailOtpDenied): env.verifier.redeem(env.original, "123456")
    env.calls.clear()
    with pytest.raises(auth.EmailOtpDenied): env.verifier.redeem({"email_verified": True}, "123456")
    assert env.calls == []


@pytest.mark.parametrize("stage", ["before", "after"])
def test_user_lookup_outage_cannot_be_bypassed(env, stage, monkeypatch):
    read = auth._read_user
    def unavailable(url, key, token):
        if (token == env.original) == (stage == "before"): raise TimeoutError("private")
        return read(url, key, token)
    monkeypatch.setattr(auth, "_read_user", unavailable)
    with pytest.raises(auth.EmailOtpUnavailable): env.verifier.redeem(env.original, "123456")


@pytest.mark.parametrize("change", [{"email": "changed@example.invalid"},
    {"email_confirmed_at": "2020-01-01T00:00:00Z"}, {"id": str(uuid4())}])
def test_address_change_or_inconsistent_fresh_snapshot_rejected(env, change):
    env.after_change = change
    with pytest.raises(auth.EmailOtpDenied): env.verifier.redeem(env.original, "123456")


def test_replay_or_aba_does_not_reuse_cached_provenance(env):
    env.verifier.redeem(env.original, "123456")
    env.error = HTTPError("redacted", 403, "consumed-or-expired", {}, None)
    env.user["email"] = "b@example.invalid"
    with pytest.raises(auth.EmailOtpDenied): env.verifier.redeem(env.original, "123456")
    env.user["email"] = "current@example.invalid"
    with pytest.raises(auth.EmailOtpDenied): env.verifier.redeem(env.original, "123456")
    assert env.calls.count("verify") == 3  # each use asks the provider; no durable proof is minted


@pytest.mark.parametrize("failure", [400, 401, 403, 422, 429, 500, 503, 302, "timeout", "json", "oversize"])
def test_provider_failure_is_fail_closed_and_redacted(env, failure, caplog):
    if isinstance(failure, int): env.error = HTTPError("private-url", failure, env.original, {}, None)
    elif failure == "timeout": env.error = TimeoutError(env.original + env.user["email"])
    else: env.raw = b"not-json" if failure == "json" else b"x"*65537
    with pytest.raises((auth.EmailOtpDenied, auth.EmailOtpUnavailable)) as error:
        env.verifier.redeem(env.original, env.code)
    rendered = "".join(traceback.format_exception(error.value)) + caplog.text
    assert all(secret not in rendered for secret in [env.original, "123456", env.user["email"], str(env.e.subject)])
    assert env.calls == ["before", "verify"]


def test_late_redemption_is_indeterminate_without_automatic_retry(env, monkeypatch):
    ticks = iter([0, 4])
    monkeypatch.setattr(auth, "monotonic", lambda: next(ticks))
    with pytest.raises(auth.EmailOtpUnavailable): env.verifier.redeem(env.original, "123456")
    assert env.calls.count("verify") == 1


def test_transport_uses_pinned_post_body_no_redirects_and_bounded_read(monkeypatch):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): assert size == 65537; return b"{}"
    class Opener:
        def open(self, request, timeout):
            assert request.get_method() == "POST" and request.full_url == ORIGIN + "/auth/v1/verify"
            assert timeout == 3 and "Authorization" not in request.headers
            assert json.loads(request.data) == {"email": "x@example.invalid", "token": "123456", "type": "email"}
            return Response()
    def opener(*handlers):
        assert any(isinstance(h, auth.ProxyHandler) and h.proxies == {} for h in handlers)
        assert any(isinstance(h, auth._NoRedirect) for h in handlers)
        return Opener()
    monkeypatch.setattr(auth, "build_opener", opener)
    assert auth._post_verify(ORIGIN + "/auth/v1/verify", "sb_publishable_test", "x@example.invalid", "123456") == b"{}"
