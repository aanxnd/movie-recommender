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
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import security, supabase_auth as auth, supabase_policy
from app.main import create_app
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
                            failure=None, worker_threads=set(), loop_threads=set())
    state.token = lambda changes=None, **kwargs: sign({"sub": str(linked[0]), **(changes or {})}, **kwargs)
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
        return original_verify(token)
    monkeypatch.setattr(verifier, "verify_claims", verify)
    def configured(*, project_url, audience, publishable_key):
        policy = supabase_policy.SupabaseAccessPolicy(project_url=project_url, audience=audience,
                                                      publishable_key=publishable_key)
        policy._verifier = verifier
        return policy
    def read_user(*args):
        if state.failure == "provider": raise TimeoutError("private diagnostics")
        return json.dumps(dict(id=str(verifier.verify(args[2])), aud="authenticated", role="authenticated",
            email="offline@example.invalid", email_confirmed_at=None if state.failure == "email" else
            "2026-01-01T00:00:00Z")).encode()
    monkeypatch.setattr(supabase_policy, "_read_user", read_user)
    monkeypatch.setattr(auth, "SupabaseAccessPolicy", configured)
    dependency = auth.make_supabase_auth_dependency(project_url=ORIGIN, audience="authenticated",
        publishable_key="sb_publishable_offline", session_factory=factory)
    assert calls == [] and state.sessions == []
    application = FastAPI()
    @application.get("/probe")
    async def probe(context: auth.SupabaseAuthContext = Depends(dependency)):
        state.loop_threads.add(get_ident())
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
        created = client.post("/users").json()
        result = client.get("/users/me", headers={"Authorization": "Bearer " + created["token"]})
        assert result.status_code == 200 and result.json() == {"id": created["id"]}
        assert client.get("/users/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401
        signed = jwt_setup[1]()
        rejected = client.get("/users/me", headers={"Authorization": "Bearer " + signed})
        assert rejected.status_code == 422  # Existing legacy header-length contract is unchanged.
        no_secrets(rejected.text, [signed])
