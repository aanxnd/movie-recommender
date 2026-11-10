"""Provider-realistic User JSON and local signed tokens; no hosted requests or credentials."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import logging
from types import SimpleNamespace
from urllib.error import HTTPError
from uuid import UUID, uuid4

import pytest

from app import supabase_email as policy
from test_supabase_jwt import ORIGIN, SUBJECT, setup as jwt_setup
from test_validation_redaction import no_secrets


@pytest.fixture
def provider(jwt_setup, monkeypatch):
    verifier, sign, _, _, jwks_calls = jwt_setup
    state = SimpleNamespace(status=200, requests=[], closed=0, failure=None, users={})
    confirmed = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    state.body = {"id": SUBJECT, "aud": "authenticated", "role": "authenticated", "email": "owner@example.invalid",
                  "email_confirmed_at": confirmed, "confirmed_at": confirmed,
                  "user_metadata": {}, "app_metadata": {"provider": "email", "providers": ["email"]}}
    class Response:
        status = 200
        def __init__(self, body): self.body = body
        def __enter__(self): return self
        def __exit__(self, *args): state.closed += 1
        def read(self, size):
            assert size == 65537
            return self.body if isinstance(self.body, bytes) else json.dumps(self.body).encode()
    class Opener:
        def open(self, request, timeout):
            state.requests.append(request)
            assert request.full_url == ORIGIN + "/auth/v1/user" and timeout == 3
            assert request.get_header("Apikey") == "sb_publishable_offline_fixture"
            assert request.get_header("Cache-control") == "no-store" and request.data is None
            if state.failure: raise state.failure
            if state.status != 200:
                raise HTTPError(request.full_url, state.status, "private diagnostic", {}, BytesIO(b'{"msg":"private"}'))
            return Response(state.users.get(request.get_header("Authorization"), state.body))
    def opener(*handlers):
        assert handlers[0].proxies == {}
        assert handlers[1].redirect_request(None, None, 302, "", {}, "https://attacker.invalid") is None
        return Opener()
    monkeypatch.setattr(policy, "build_opener", opener)
    state.client = policy.ProviderEmailPolicy(project_url=ORIGIN, audience="authenticated",
                                             publishable_key="sb_publishable_offline_fixture")
    state.client._verifier = verifier
    state.sign, state.jwks_calls = sign, jwks_calls
    assert state.requests == [] and jwks_calls == []
    return state


def test_fresh_provider_marker_bound_to_verified_subject(provider):
    token = provider.sign({"email": "stale@example.invalid"})
    first = provider.client.check(token)
    assert first.subject == UUID(SUBJECT) and first.confirmed_at <= first.observed_at
    assert first.email == "owner@example.invalid" and not hasattr(first, "active") and not hasattr(first, "aal")
    assert SUBJECT not in repr(first)
    with pytest.raises(FrozenInstanceError): first.subject = UUID(int=0)
    if provider.requests[0].get_header("Authorization") != "Bearer " + token:
        pytest.fail("Credential binding failed", pytrace=False)
    provider.body["email_confirmed_at"] = None
    with pytest.raises(policy.EmailConfirmationDenied): provider.client.check(token)
    assert len(provider.requests) == 2 and len(provider.jwks_calls) == 1 and provider.closed == 2


@pytest.mark.parametrize("changes", [
    {"email_confirmed_at": None}, {"email_confirmed_at": True}, {"email_confirmed_at": ""},
    {"email_confirmed_at": "not-a-date"}, {"email_confirmed_at": "2026-01-01T00:00:00"},
    {"email_confirmed_at": "9999-01-01T00:00:00Z"}, {"email": None}, {"email": True},
    {"email": ""}, {"email": "not-an-email"}, {"id": "00000000-0000-0000-0000-000000000000"},
    {"email_confirmed_at": None, "phone_confirmed_at": "2026-01-01T00:00:00Z"},
    {"email_confirmed_at": None, "user_metadata": {"email_verified": True}},
])
def test_missing_malformed_or_conflicting_evidence_denied(provider, changes):
    provider.body.update(changes)
    # Extra email_verified is a spoofing attempt, not a documented Supabase JWT claim.
    token = provider.sign({"email_verified": True, "user_metadata": {"email_verified": True}, "aal": "aal2"})
    with pytest.raises(policy.EmailConfirmationDenied, match="^Email confirmation evidence rejected$"):
        provider.client.check(token)


@pytest.mark.parametrize("field", ["id", "email", "email_confirmed_at"])
def test_required_provider_fields_cannot_be_substituted_with_claims(provider, field):
    del provider.body[field]
    with pytest.raises(policy.EmailConfirmationDenied): provider.client.check(provider.sign())


@pytest.mark.parametrize("status", [401, 403, 404])
def test_provider_rejection_including_deleted_banned_or_revoked_is_not_overridden(provider, status, caplog):
    provider.status = status
    token = provider.sign({"aal": "aal2"})
    caplog.set_level(logging.DEBUG)
    with pytest.raises(policy.EmailConfirmationDenied) as error: provider.client.check(token)
    assert str(error.value) == "Email confirmation evidence rejected" and error.value.__suppress_context__
    no_secrets(str(error.value) + caplog.text, [token, SUBJECT, "private", "owner@example.invalid"])


@pytest.mark.parametrize("kind", ["timeout", "rate-limit", "server", "redirect", "json", "oversized", "jwks"])
def test_outage_or_unusable_provider_response_has_no_stale_fallback(provider, kind, caplog):
    token = provider.sign()
    if kind == "timeout": provider.failure = TimeoutError("private diagnostic")
    if kind in {"rate-limit", "server", "redirect"}: provider.status = {"rate-limit": 429, "server": 500, "redirect": 302}[kind]
    if kind == "json": provider.body = b"not JSON"
    if kind == "oversized": provider.body = b" " * 65537
    if kind == "jwks":
        def unavailable(url): raise TimeoutError("private diagnostic")
        provider.client._verifier._fetch = unavailable
    caplog.set_level(logging.DEBUG)
    with pytest.raises(policy.EmailEvidenceUnavailable) as error: provider.client.check(token)
    assert str(error.value) == "Email confirmation evidence unavailable" and error.value.__suppress_context__
    no_secrets(str(error.value) + caplog.text, [token, SUBJECT, "private", "owner@example.invalid"])
    if kind == "jwks": assert provider.requests == []


@pytest.mark.parametrize("token", [None, True, {"email_verified": True}, "legacy" * 8, "abc.def.ghi"])
def test_caller_booleans_claims_and_invalid_tokens_never_reach_provider(provider, token):
    with pytest.raises(policy.EmailConfirmationDenied): provider.client.check(token)
    assert provider.requests == []


def test_expired_token_or_previous_evidence_cannot_substitute_for_live_check(provider):
    with pytest.raises(policy.EmailConfirmationDenied): provider.client.check(provider.sign({"exp": 1}))
    assert provider.requests == []
    evidence = provider.client.check(provider.sign())
    with pytest.raises(policy.EmailConfirmationDenied): provider.client.check(evidence)
    assert len(provider.requests) == 1


@pytest.mark.parametrize("aal", ["aal1", "aal2", None, "invented"])
def test_email_evidence_never_establishes_mfa_or_current_session(provider, aal):
    # Even malformed assurance cannot become an MFA proof through an email result.
    evidence = provider.client.check(provider.sign({"aal": aal}))
    assert not hasattr(evidence, "aal") and not hasattr(evidence, "session_active")
    provider.body["user_metadata"] = {"email_verified": False, "aal": "aal2"}
    assert provider.client.check(provider.sign()).subject == evidence.subject


def test_concurrent_requests_keep_bearer_headers_request_local(provider):
    subjects = [str(uuid4()) for _ in range(6)]
    tokens = [provider.sign({"sub": subject}) for subject in subjects]
    provider.users = {"Bearer " + token: {**provider.body, "id": subject} for token, subject in zip(tokens, subjects)}
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert [str(e.subject) for e in pool.map(provider.client.check, tokens)] == subjects
    assert len(provider.requests) == 6 and provider.closed == 6 and len(provider.jwks_calls) == 1


@pytest.mark.parametrize("key", [None, "service_role", "sb_secret_private", "ey.fake.admin", "sb_publishable_bad\r\nX: y"])
def test_privileged_or_malformed_key_configuration_is_rejected(key):
    with pytest.raises(ValueError, match="^Expected a public publishable API key$"):
        policy.ProviderEmailPolicy(project_url=ORIGIN, audience="authenticated", publishable_key=key)
