"""Prompt 22: real legacy routes and isolated numeric-data/token-boundary regressions."""
import logging
import secrets
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import database, security, supabase_auth
from app.main import create_app
from app.models import Credential, GroupInvitation, User, UserIdentity, UserRating
from app.migrations import migrate
from app.supabase_identity import UnresolvedIdentity, resolve_verified_subject
from app.supabase_jwt import InvalidAccessToken
from test_api import api_paths
from test_postgresql_concurrency import pg_engine
from test_supabase_claims import evidence
from test_user_identities import identity_engine


def snapshot(session):
    return tuple(tuple(tuple(row) for row in session.execute(select(model.__table__).order_by(model.user_id if
                 hasattr(model, "user_id") else model.id))) for model in
                 (User, Credential, UserIdentity, UserRating, GroupInvitation))


def test_live_creation_restore_ownership_and_data_survive_wrong_provider_tokens(api_paths, evidence, monkeypatch, caplog):
    def dormant(*args, **kwargs):
        pytest.fail("Production attempted to activate dormant authentication")
    monkeypatch.setattr(supabase_auth, "make_supabase_auth_dependency", dormant)
    caplog.set_level(logging.INFO)
    application = create_app(*api_paths)
    with TestClient(application) as client:
        first, second = client.post("/users").json(), client.post("/users").json()
        owner = {"Authorization": "Bearer " + first["token"]}
        peer = {"Authorization": "Bearer " + second["token"]}
        assert security.TOKEN_PATTERN.fullmatch(first["token"])
        assert first["expires_at"] > 0 and first["id"] != second["id"]
        assert client.get("/users/me", headers=owner).json() == {"id": first["id"]}
        assert client.put(f'/users/{first["id"]}/ratings/1', headers=owner, json={"rating": 4}).status_code == 200
        invitation = client.post(f'/users/{second["id"]}/group-invitation', headers=peer).json()["code"].split(":")[1]
        group = {"user_ids": [first["id"], second["id"]], "invitations": {str(second["id"]): invitation}}
        assert client.post("/recommendations/group", headers=owner, json=group).status_code == 200
        with Session(application.state.engine) as session, session.begin():
            # Even a valid existing future link must not activate JWT acceptance on live routes.
            session.add(UserIdentity(user_id=second["id"], supabase_subject=evidence.subject, username="SignedUser"))
        with Session(application.state.engine) as session:
            before = snapshot(session)
        signed = evidence.sign()
        assert evidence.verifier.verify_claims(signed).subject == evidence.subject
        for token, expected in [(signed, 422), ("abc.def.ghi", 401), ("x" * 43, 401)]:
            response = client.get("/users/me", headers={"Authorization": "Bearer " + token})
            assert response.status_code == expected  # Preserve the existing max-100 legacy header contract.
            if token in response.text:
                raise AssertionError("Authentication input leaked through an error")
        assert client.get(f'/users/{first["id"]}/ratings', headers=peer).status_code == 403
        assert client.get("/movies/search?q=First").status_code == 200
        assert client.get("/recommendations/popular").status_code == 200
        assert client.get("/users/me", headers=owner).json() == {"id": first["id"]}
        assert client.get(f'/users/{first["id"]}/ratings', headers=owner).json()[0]["rating"] == 4
        with Session(application.state.engine) as session:
            assert snapshot(session) == before
        if any(value in caplog.text for value in (first["token"], second["token"], signed, invitation)):
            raise AssertionError("Authentication material leaked through logging")


@pytest.mark.parametrize("kind", ["opaque", "legacy-envelope", "hs256", "wrong-issuer"])
def test_token_kinds_do_not_fall_back_or_select_a_local_user(identity_engine, evidence, monkeypatch, kind):
    with Session(identity_engine) as session, session.begin():
        user_id = database.create_user(session).id
        token, _ = security.issue_credential(session, user_id)
        session.add(UserIdentity(user_id=user_id, username="SameName"))
    value = token if kind == "opaque" else f"{user_id}:{token}" if kind == "legacy-envelope" else (
        jwt.encode({"sub": str(evidence.subject), "email": "offline@example.invalid", "user_id": user_id},
                   secrets.token_bytes(32), algorithm="HS256") if kind == "hs256" else evidence.sign({"iss": "https://wrong.invalid/auth/v1"}))
    with Session(identity_engine) as session:
        before = snapshot(session)
        monkeypatch.setattr(security, "authenticate", lambda *a: pytest.fail("Legacy fallback invoked"))
        with pytest.raises(InvalidAccessToken):
            evidence.verifier.verify_claims(value)
        assert snapshot(session) == before


def test_isolated_lookup_and_migration_preserve_existing_owners_without_claiming(identity_engine, evidence):
    first_subject, unknown = evidence.subject, uuid4()
    with Session(identity_engine) as session, session.begin():
        first, legacy = [database.create_user(session).id for _ in range(2)]
        database.register_movies(session, [1])
        database.save_rating(session, legacy, 1, 4.5)
        token, _ = security.issue_credential(session, legacy)
        invitation, _ = security.issue_invitation(session, legacy)
        session.add_all([UserIdentity(user_id=first, supabase_subject=first_subject, username="Linked"),
                         UserIdentity(user_id=legacy, username="SameName")])
    with Session(identity_engine) as session:
        before = snapshot(session)
        for claims in ({"sub": str(unknown), "user_id": legacy, "username": "SameName", "email": "offline@example.invalid"},
                       {"sub": str(first_subject), "user_id": legacy, "username": "SameName"}):
            verified = evidence.verifier.verify_claims(evidence.sign(claims))
            if verified.subject == unknown:
                with pytest.raises(UnresolvedIdentity): resolve_verified_subject(session, verified.subject)
            else:
                assert resolve_verified_subject(session, verified.subject).user_id == first
        assert security.authenticate(session, "Bearer " + token) == legacy
        assert session.get(GroupInvitation, legacy).token_hash == security.token_hash(invitation)
        assert snapshot(session) == before
    migrate(identity_engine)  # Existing idempotent migration, isolated DB only; no new migration.
    with Session(identity_engine) as session, session.begin():
        assert snapshot(session) == before
        assert database.create_user(session).id > max(first, legacy)
