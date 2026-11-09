"""Mock trusted readers are test-only attestations, never hosted security evidence."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import json
import traceback
from types import SimpleNamespace
from urllib.error import HTTPError
from uuid import uuid4

import pytest

from app import supabase_evidence as auth
from test_supabase_claims import evidence as jwt_evidence
from test_supabase_jwt import ORIGIN


@pytest.fixture
def env(jwt_evidence, monkeypatch):
    e = jwt_evidence
    now = datetime.fromtimestamp(e.now+1, timezone.utc)
    confirmed = now-timedelta(days=1)
    state = SimpleNamespace(jwt=e, now=now, confirmed=confirmed, calls=[], live_change={}, proof_change={},
                            live_missing=False, proof_missing=False, error=None, raw=None, old=None)
    state.user = dict(id=str(e.subject), aud="authenticated", role="authenticated",
                      email="mailbox@example.invalid", email_confirmed_at=confirmed.isoformat(), is_anonymous=False)
    def fetch(url, key, token):
        assert url == ORIGIN + "/auth/v1/user" and key == "sb_publishable_test" and token == state.token
        state.calls.append("user")
        if state.error: raise state.error
        return state.raw if state.raw is not None else json.dumps(state.user).encode()
    class Live:
        def read(self, **request):
            state.calls.append("live")
            assert request["subject"] == e.subject and request["session_id"] == e.session_id
            if state.live_missing: return None
            if state.old is not None: return state.old
            value = auth.LiveAccountSession(request["issuer"], request["subject"], request["session_id"],
                request["nonce"], state.now, "mailbox@example.invalid", confirmed, "enabled", "present")
            state.last = replace(value, **state.live_change)
            return state.last
    class Mailbox:
        def read(self, **request):
            state.calls.append("mailbox")
            if state.proof_missing: return None
            value = auth.MailboxChallenge(request["issuer"], request["subject"], "mailbox@example.invalid",
                                          confirmed, now-timedelta(hours=1), now+timedelta(hours=1))
            return replace(value, **state.proof_change)
    monkeypatch.setattr(auth, "_read_user", fetch)
    monkeypatch.setattr(auth, "_now", lambda: state.now)
    def configured(project_url, *, audience):
        assert project_url == ORIGIN and audience == "authenticated"
        return e.verifier
    monkeypatch.setattr(auth, "SupabaseTokenVerifier", configured)
    state.mailbox, state.live = Mailbox(), Live()
    state.policy = auth.AuthenticationEvidencePolicy(project_url=ORIGIN, audience="authenticated",
        publishable_key="sb_publishable_test", mailbox=state.mailbox, live_state=state.live)
    state.token = e.sign()
    assert state.calls == [] and e.calls == []
    return state


def denied(env):
    with pytest.raises(auth.AuthenticationEvidenceDenied, match="^Authentication evidence rejected$"):
        env.policy.check(env.token)


def test_complete_binding_immutability_and_no_positive_cache(env):
    result = env.policy.check(env.token)
    assert result.claims.subject == env.jwt.subject and result.claims.session_id == env.jwt.session_id
    assert result.observed_at == env.now
    with pytest.raises(FrozenInstanceError): result.observed_at = env.confirmed
    assert str(env.jwt.subject) not in repr(result) and "mailbox@" not in repr(result)
    env.policy.check(env.token)
    assert env.calls == ["user", "live", "mailbox"]*2
    env.live_change = {"session_state": "revoked"}
    denied(env)
    assert env.calls[-2:] == ["user", "live"]


@pytest.mark.parametrize("field,value", [("id", str(uuid4())), ("aud", "wrong"), ("role", "service_role"),
    ("email", ""), ("email_confirmed_at", None), ("email_confirmed_at", "bad"),
    ("email_confirmed_at", "2025-01-01"), ("deleted_at", "2025-01-01T00:00:00Z"),
    ("is_anonymous", True), ("banned_until", "9999-01-01T00:00:00Z")])
def test_inconsistent_unconfirmed_or_inactive_provider_user(env, field, value):
    env.user[field] = value
    denied(env)


@pytest.mark.parametrize("field", ["id", "aud", "role", "email", "email_confirmed_at", "is_anonymous"])
def test_missing_provider_evidence_denies(env, field):
    del env.user[field]
    denied(env)


@pytest.mark.parametrize("field,value", [("subject", uuid4()), ("session_id", uuid4()), ("nonce", uuid4()),
    ("issuer", "other"), ("account_state", "deleted"), ("account_state", "banned"),
    ("account_state", "disabled"), ("account_state", "unknown"), ("session_state", "revoked"),
    ("session_state", "missing"), ("session_state", "unknown"), ("email", "old@example.invalid")])
def test_live_binding_and_authoritative_state_required(env, field, value):
    env.live_change[field] = value
    denied(env)


@pytest.mark.parametrize("source", ["proof", "live"])
def test_missing_unknown_or_forged_source_record_denies(env, source):
    setattr(env, source + "_missing", True)
    denied(env)
    reader = env.mailbox if source == "proof" else env.live
    reader.read = lambda **kwargs: {"verified": True, "active": True}
    denied(env)


@pytest.mark.parametrize("field", ["subject", "issuer", "email", "confirmed_at", "verified_at", "valid_until"])
def test_untrusted_mismatched_expired_or_future_mailbox_evidence(env, field):
    env.proof_change[field] = {"subject": uuid4(), "issuer": "other", "email": "other@example.invalid",
        "confirmed_at": env.confirmed-timedelta(seconds=1), "verified_at": env.now+timedelta(seconds=1),
        "valid_until": env.now}[field]
    denied(env)


def test_confirmed_but_unproven_history_and_email_changes_deny(env):
    env.token = env.jwt.sign({"email_verified": True, "email": "mailbox@example.invalid"})
    env.user["user_metadata"] = {"email_verified": True}
    env.proof_missing = True  # administrative/implicit confirmation supplies no genuine attestation
    denied(env)
    env.proof_missing = False
    env.user["email"] = "changed@example.invalid"
    env.live_change["email"] = env.user["email"]
    denied(env)  # even live matching email cannot reuse old mailbox proof
    env.user["email"] = "mailbox@example.invalid"
    env.live_change = {}
    env.proof_missing = True  # trusted ledger must revoke old proof even on A -> B -> A
    denied(env)


def test_stale_future_naive_and_replayed_observations_deny(env):
    for instant in [env.now-timedelta(seconds=1), env.now+timedelta(seconds=1), env.now.replace(tzinfo=None)]:
        env.live_change = {"observed_at": instant}
        denied(env)
    env.live_change = {}
    env.policy.check(env.token)
    env.old = env.last
    denied(env)  # new per-check nonce rejects replay even with a frozen clock


@pytest.mark.parametrize("value", [b"not-json", b"[]", b'{"id":1,"id":2}', b"x"*65537],
                         ids=["json", "array", "duplicate", "oversized"])
def test_malformed_provider_response(env, value):
    env.raw = value
    with pytest.raises((auth.AuthenticationEvidenceDenied, auth.AuthenticationEvidenceUnavailable)):
        env.policy.check(env.token)


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 503, 302])
def test_provider_errors_are_generic_and_secret_free(env, status, caplog):
    env.error = HTTPError("private-url", status, env.token, {}, None)
    expected = auth.AuthenticationEvidenceDenied if status in (401, 403, 404) else auth.AuthenticationEvidenceUnavailable
    with pytest.raises(expected) as error: env.policy.check(env.token)
    rendered = "".join(traceback.format_exception(error.value)) + caplog.text
    assert all(value not in rendered for value in [env.token, env.user["email"], str(env.jwt.subject), "private-url"])
    assert env.calls == ["user"]


@pytest.mark.parametrize("source", ["user", "live", "mailbox"])
def test_network_or_adapter_outage_never_falls_back(env, source, caplog):
    diagnostic = env.token + json.dumps(env.user)
    def timeout(**kwargs): raise TimeoutError(diagnostic)
    if source == "user": env.error = TimeoutError(diagnostic)
    else: getattr(env, source).read = timeout
    with pytest.raises(auth.AuthenticationEvidenceUnavailable, match="^Authentication evidence unavailable$") as error:
        env.policy.check(env.token)
    assert diagnostic not in "".join(traceback.format_exception(error.value)) + caplog.text


def test_no_missing_adapter_jwt_only_or_caller_claim_fallback(env):
    policy = auth.AuthenticationEvidencePolicy(project_url=ORIGIN, audience="authenticated", publishable_key="sb_publishable_test")
    with pytest.raises(auth.AuthenticationEvidenceDenied): policy.check(env.token)
    for value in ["x"*43, {"sub": str(env.jwt.subject), "email_verified": True}, env.jwt.verifier.verify_claims(env.token)]:
        with pytest.raises(auth.AuthenticationEvidenceDenied): env.policy.check(value)
    assert env.calls == []


def test_late_evidence_or_jwt_expiry_cannot_succeed(env, monkeypatch):
    ticks = iter([0, 4])
    monkeypatch.setattr(auth, "monotonic", lambda: next(ticks))
    with pytest.raises(auth.AuthenticationEvidenceUnavailable): env.policy.check(env.token)


def test_jwt_expiring_during_evidence_reads_denies(env):
    original = env.mailbox.read
    def late(**request):
        value = original(**request)
        env.now += timedelta(seconds=601)
        return value
    env.mailbox.read = late
    with pytest.raises(auth.AuthenticationEvidenceUnavailable): env.policy.check(env.token)
