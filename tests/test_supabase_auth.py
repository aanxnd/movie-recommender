"""Test-only FastAPI routes; real local signatures and disposable database links."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import logging
import json
from threading import Event, get_ident
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy import delete
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import security, supabase_auth as auth, supabase_policy
from app.main import create_app
from app.models import User, UserIdentity
from test_api import api_paths
from test_postgresql_concurrency import pg_engine
from test_supabase_identity import engine, linked
from test_supabase_jwt import ORIGIN, setup as jwt_setup
from test_supabase_claims import evidence
from test_validation_redaction import no_secrets


@pytest.fixture
def environment(engine, linked, evidence, monkeypatch):
    verifier, sign, calls = evidence.verifier, evidence.sign, evidence.calls
    state = SimpleNamespace(engine=engine, verifier=verifier, calls=calls, sessions=[], subjects=linked,
                            failure=None, worker_threads=set(), loop_threads=set(), principals=[],
                            provider_requests=[], overrides={}, omitted=set(), raw=None, error=None, order=[])
    subjects_by_token = {}
    def token(changes=None, **kwargs):
        claims = {"sub": str(linked[0]), **(changes or {})}
        value = sign(claims, **kwargs)
        subjects_by_token[value] = claims["sub"]
        return value
    state.token = token
    state.subject = str(linked[0])
    def unavailable():
        raise OperationalError("private SQL", {}, Exception("private diagnostics"))
    class TrackedSession(Session):
        def __init__(self):
            super().__init__(engine)
            self.owner_thread, self.closed, self.committed, self.rolled_back = get_ident(), False, 0, 0
            state.sessions.append(self)
            event.listen(self, "after_commit", lambda _: setattr(self, "committed", self.committed + 1))
            event.listen(self, "after_rollback", lambda _: setattr(self, "rolled_back", self.rolled_back + 1))
            event.listen(self, "before_commit", lambda _: unavailable() if state.failure == "commit" else None)
        def execute(self, *args, **kwargs):
            if state.failure == "query": unavailable()
            return super().execute(*args, **kwargs)
        def close(self):
            assert get_ident() == self.owner_thread
            self.closed = True
            super().close()
    def factory():
        if state.failure == "factory": unavailable()
        return TrackedSession()
    original_verify = verifier.verify_claims
    def verify(token):
        state.worker_threads.add(get_ident())
        state.order.append("jwt")
        return original_verify(token)
    monkeypatch.setattr(verifier, "verify_claims", verify)
    def configured(*, project_url, audience, publishable_key):
        policy = supabase_policy.SupabaseAccessPolicy(project_url=project_url, audience=audience,
                                                      publishable_key=publishable_key)
        policy._verifier = verifier
        return policy
    def read_user(*args):
        state.order.append("provider")
        state.provider_requests.append(args)
        assert args[:2] == (ORIGIN + "/auth/v1/user", "sb_publishable_offline")
        if state.failure == "provider": raise TimeoutError("private diagnostics")
        if state.error: raise state.error
        user = dict(id=subjects_by_token[args[2]], aud="authenticated", role="authenticated", is_anonymous=False,
            email="offline@example.invalid", email_confirmed_at=None if state.failure == "email" else
            "2026-01-01T00:00:00Z", factors=[])
        user.update(state.overrides)
        for name in state.omitted: user.pop(name, None)
        return state.raw if state.raw is not None else json.dumps(user).encode()
    original_resolve = auth.resolve_verified_subject
    def resolve(session, subject):
        state.order.append("identity")
        return original_resolve(session, subject)
    monkeypatch.setattr(auth, "resolve_verified_subject", resolve)
    monkeypatch.setattr(supabase_policy, "_read_user", read_user)
    monkeypatch.setattr(auth, "SupabaseAccessPolicy", configured)
    dependency = auth.make_supabase_auth_dependency(project_url=ORIGIN, audience="authenticated",
        publishable_key="sb_publishable_offline", session_factory=factory)
    state.dependency = dependency  # Reused by isolated resource-authorization routes.
    assert calls == [] and state.sessions == []
    application = FastAPI()
    @application.get("/probe")
    async def probe(context: auth.SupabaseAuthContext = Depends(dependency)):
        state.loop_threads.add(get_ident())
        state.principals.append(context)
        with pytest.raises(FrozenInstanceError): context.user_id = 207
        return {"user_id": context.user_id}
    @application.get("/ping")
    async def ping(): return {"ok": True}
    state.app = application
    monkeypatch.setattr(security, "authenticate", lambda *args: pytest.fail("Legacy fallback invoked"))
    yield state
    assert all(session.closed and not session.in_transaction() for session in state.sessions)
    assert engine.pool.checkedout() == 0


def test_valid_context_cannot_select_another_user(environment):
    state = environment
    with TestClient(state.app) as client:
        result = client.get("/probe?user_id=207&username=Second", headers={"Authorization": "bEaReR " + state.token()})
    assert result.status_code == 200 and result.json() == {"user_id": 104}
    assert result.headers["cache-control"] == "no-store"
    assert state.sessions[0].committed == 1
    assert state.worker_threads.isdisjoint(state.loop_threads)


@pytest.mark.parametrize("aal", ["aal1", "aal2"])
def test_principal_uses_current_email_and_verified_binding_once_per_request(environment, aal, caplog):
    state = environment
    if aal == "aal2":
        state.overrides["factors"] = [dict(id=str(uuid4()), factor_type="totp", status="verified")]
    state.overrides.update(new_email="pending@example.invalid", email_change_sent_at="2026-01-01T00:00:00Z")
    token = state.token({"aal": aal, "email": "stale@example.invalid"})
    with TestClient(state.app) as client, caplog.at_level(logging.DEBUG):
        for _ in range(2):
            result = client.get("/probe?user_id=207",
                                headers={"Authorization": "Bearer " + token, "X-User-Id": "207",
                                         "X-User-Email": "pending@example.invalid"})
            assert result.status_code == 200 and result.json() == {"user_id": 104}
    principal = state.principals[-1]
    assert (principal.subject, principal.user_id, principal.email, principal.aal) == (
        state.subjects[0], 104, "offline@example.invalid", aal)
    assert not hasattr(principal, "__dict__") and not hasattr(principal, "token")
    for field in ("subject", "email", "aal"):
        with pytest.raises(FrozenInstanceError): setattr(principal, field, None)
    no_secrets(repr(principal) + caplog.text, [token, state.subject, principal.email, "pending@example.invalid"])
    assert state.order == ["jwt", "provider", "identity"] * 2
    assert len(state.provider_requests) == 2 and len(state.calls) == 1


@pytest.mark.parametrize("change", [
    {"id": str(uuid4())}, {"email_confirmed_at": None}, {"email_confirmed_at": "invalid"},
    {"email_confirmed_at": "2999-01-01T00:00:00Z"}, {"new_email": None},
    {"is_anonymous": True}, {"is_anonymous": None}, {"is_anonymous": 0},
    {"banned_until": "2999-01-01T00:00:00Z"}, {"deleted_at": "2026-01-01T00:00:00Z"},
    {"role": "service_role"}, {"aud": "other"}, {"factors": None}, {"factors": {}}, {"factors": [None]},
])
def test_ineligible_or_incomplete_provider_evidence_denies_before_neon(environment, change):
    state = environment
    state.overrides.update(change)
    with TestClient(state.app) as client:
        result = client.get("/probe", headers={"Authorization": "Bearer " + state.token({"aal": "aal2"})})
    assert result.status_code == 401 and result.json() == {"detail": "Invalid authentication credentials"}
    assert state.order == ["jwt", "provider"] and state.sessions == [] and state.principals == []


@pytest.mark.parametrize("field", ["is_anonymous", "email", "email_confirmed_at"])
def test_omitted_security_evidence_never_becomes_permission(environment, field):
    state = environment
    state.omitted.add(field)
    with TestClient(state.app) as client:
        assert client.get("/probe", headers={"Authorization": "Bearer " + state.token()}).status_code == 401
    assert state.sessions == []


@pytest.mark.parametrize("status,aal,allowed", [("verified", "aal1", False), ("verified", "aal2", True),
                                                ("unverified", "aal1", True)])
def test_principal_enforces_totp_assurance(environment, status, aal, allowed):
    state = environment
    state.overrides["factors"] = [dict(id=str(uuid4()), factor_type="totp", status=status)]
    with TestClient(state.app) as client:
        result = client.get("/probe", headers={"Authorization": "Bearer " + state.token({"aal": aal})})
    assert result.status_code == (200 if allowed else 401)
    assert len(state.sessions) == int(allowed)
    if allowed: assert state.principals[-1].aal == aal


@pytest.mark.parametrize("raw,status", [(b"invalid", 503), (b"[]", 401), (b'{"email":"a","email":"b"}', 503)])
def test_unusable_provider_json_has_generic_errors(environment, raw, status, caplog):
    state = environment
    state.raw = raw
    token = state.token()
    with TestClient(state.app) as client, caplog.at_level(logging.DEBUG):
        result = client.get("/probe", headers={"Authorization": "Bearer " + token})
    assert result.status_code == status and state.sessions == []
    no_secrets(result.text + caplog.text, [token, state.subject, "offline@example.invalid"])


@pytest.mark.parametrize("status", [403, 429, 500])
def test_provider_rejection_or_outage_never_reuses_a_prior_principal(environment, status):
    from urllib.error import HTTPError
    state = environment
    token = state.token()
    with TestClient(state.app) as client:
        assert client.get("/probe", headers={"Authorization": "Bearer " + token}).status_code == 200
        state.error = HTTPError("redacted", status, "private diagnostics", {}, None)
        result = client.get("/probe", headers={"Authorization": "Bearer " + token})
    assert result.status_code == (401 if status == 403 else 503)
    assert len(state.principals) == len(state.sessions) == 1 and len(state.provider_requests) == 2


@pytest.mark.parametrize("delete_user", [False, True])
def test_removed_mapping_or_user_cannot_reuse_prior_principal(environment, delete_user):
    state = environment
    with Session(state.engine) as session, session.begin():
        session.execute(delete(UserIdentity).where(UserIdentity.user_id == 104))
        if delete_user: session.execute(delete(User).where(User.id == 104))
    with TestClient(state.app) as client:
        assert client.get("/probe", headers={"Authorization": "Bearer " + state.token()}).status_code == 401
    assert state.order == ["jwt", "provider", "identity"] and state.principals == []


def test_token_expiring_during_local_lookup_cannot_return_principal(environment, evidence, monkeypatch):
    state = environment
    monkeypatch.setattr(auth, "time", lambda: evidence.now + 601)
    with TestClient(state.app) as client:
        assert client.get("/probe", headers={"Authorization": "Bearer " + state.token()}).status_code == 401
    assert state.order == ["jwt", "provider", "identity"] and len(state.sessions) == 1
    assert state.principals == []


def test_unconfirmed_email_denied_before_local_identity_lookup(environment):
    state = environment
    state.failure = "email"
    with TestClient(state.app) as client:
        result = client.get("/probe", headers={"Authorization": "Bearer " + state.token()})
    assert result.status_code == 401 and state.sessions == []


@pytest.mark.parametrize("kind", ["missing", "empty", "basic", "bare", "scheme-only", "double-space", "tab",
    "leading", "trailing", "combined", "multiple", "duplicate", "conflicting", "legacy", "oversized"])
def test_ambiguous_headers_rejected_before_verification_or_database(environment, kind):
    state = environment
    value = "Bearer " + state.token()
    headers = {"missing": [], "empty": [("Authorization", "")], "basic": [("Authorization", "Basic abc")],
        "bare": [("Authorization", value[7:])], "multiple": [("Authorization", value + " " + value)],
        "scheme-only": [("Authorization", "Bearer")], "double-space": [("Authorization", value.replace(" ", "  "))],
        "tab": [("Authorization", value.replace(" ", "\t"))], "leading": [("Authorization", " " + value)],
        "trailing": [("Authorization", value + " ")], "combined": [("Authorization", value + ", " + value)],
        "duplicate": [("Authorization", value), ("AUTHORIZATION", value)],
        "conflicting": [("Authorization", value), ("Authorization", "Bearer x.y.z")],
        "legacy": [("Authorization", "Bearer " + "x" * 43)], "oversized": [("Authorization", "Bearer " + "x" * 8193)]}[kind]
    with TestClient(state.app) as client: result = client.get("/probe?user_id=104", headers=headers)
    assert result.status_code == 401 and result.json() == {"detail": "Invalid authentication credentials"}
    assert result.headers["www-authenticate"] == "Bearer" and result.headers["cache-control"] == "no-store"
    assert state.worker_threads == set() and state.calls == [] and state.sessions == []


@pytest.mark.parametrize("kind", ["expired", "signature", "issuer", "audience", "unknown", "legacy-format"])
def test_invalid_credentials_have_generic_secret_safe_errors(environment, kind, caplog):
    state = environment
    changes = {"expired": {"exp": 1}, "issuer": {"iss": ORIGIN}, "audience": {"aud": "other"},
               "unknown": {"sub": str(uuid4())}}.get(kind, {})
    token = state.token(changes, key=ec.generate_private_key(ec.SECP256R1())) if kind == "signature" else state.token(changes)
    if kind == "legacy-format": token = "abc.def.ghi"
    caplog.set_level(logging.DEBUG)
    with TestClient(state.app) as client: result = client.get("/probe", headers={"Authorization": "Bearer " + token})
    assert result.status_code == 401 and result.json() == {"detail": "Invalid authentication credentials"}
    secrets = [token, state.subject, "private diagnostics"]
    if "sub" in changes: secrets.append(changes["sub"])
    no_secrets(result.text + caplog.text, secrets)
    assert len(state.sessions) == (1 if kind == "unknown" else 0)
    if state.sessions: assert state.sessions[0].rolled_back == 1


@pytest.mark.parametrize("kind", ["keys", "provider", "factory", "query", "commit"])
def test_outages_fail_closed_and_clean_up(environment, kind, caplog):
    state = environment
    state.failure = kind
    def fail(url): raise TimeoutError("private diagnostics")
    if kind == "keys": state.verifier._fetch = fail
    token = state.token()
    caplog.set_level(logging.DEBUG)
    with TestClient(state.app) as client: result = client.get("/probe", headers={"Authorization": "Bearer " + token})
    assert result.status_code == 503 and result.json() == {"detail": "Authentication temporarily unavailable"}
    assert result.headers["retry-after"] == "30" and result.headers["cache-control"] == "no-store"
    no_secrets(result.text + caplog.text, [token, state.subject, "private SQL", "private diagnostics"])
    assert len(state.sessions) == (1 if kind in {"query", "commit"} else 0)
    if state.sessions: assert state.sessions[0].rolled_back == 1


def test_concurrent_requests_share_verifier_but_not_sessions(environment):
    state = environment
    tokens = [state.token({"sub": str(state.subjects[index % 2])}) for index in range(6)]
    with TestClient(state.app) as client, ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda token: client.get("/probe", headers={"Authorization": "Bearer " + token}), tokens))
    assert all(result.status_code == 200 and result.json() == {"user_id": [104, 207][index % 2]}
               for index, result in enumerate(results))
    assert len(state.calls) == 1 and len({id(session) for session in state.sessions}) == 6
    assert state.worker_threads.isdisjoint(state.loop_threads)


def test_slow_jwks_does_not_block_async_event_loop(environment):
    state = environment
    started, release = Event(), Event()
    original = state.verifier._fetch
    def slow(url):
        started.set()
        assert release.wait(5)
        return original(url)
    state.verifier._fetch = slow
    with TestClient(state.app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(client.get, "/probe", headers={"Authorization": "Bearer " + state.token()})
        try:
            assert started.wait(2)
            assert pool.submit(client.get, "/ping").result(timeout=2).status_code == 200
        finally:
            release.set()
        assert pending.result(timeout=3).status_code == 200


def test_existing_app_requires_no_supabase_configuration_or_new_dependency(api_paths, monkeypatch, jwt_setup):
    for name in ("SUPABASE_URL", "SUPABASE_AUDIENCE"): monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(auth, "SupabaseAccessPolicy", lambda *a, **kw: pytest.fail("Dormant dependency activated"))
    application = create_app(*api_paths)
    assert "/probe" not in application.openapi()["paths"]
    with TestClient(application) as client:
        assert client.get("/movies/search?q=First").status_code == 200
        created = client.post("/users").json()
        result = client.get("/users/me", headers={"Authorization": "Bearer " + created["token"]})
        assert result.status_code == 200 and result.json() == {"id": created["id"]}
        assert client.get("/users/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401
        signed = jwt_setup[1]()
        rejected = client.get("/users/me", headers={"Authorization": "Bearer " + signed})
        assert rejected.status_code == 422  # Existing legacy header-length contract is unchanged.
        no_secrets(rejected.text, [signed])
