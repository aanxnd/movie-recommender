"""Real isolated storage and test-only JWT-authenticated routes; no hosted access."""
import logging
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import database, resource_authorization as access
from app.models import UserIdentity, UserRating
from app.schemas import RatingRequest
from app.supabase_auth import SupabaseAuthContext
from test_supabase_auth import environment, engine, linked, pg_engine, evidence
from test_validation_redaction import no_secrets


@pytest.fixture
def resources(environment):
    state = environment
    state.principal = SupabaseAuthContext(user_id=104, subject=state.subjects[0], email="offline@example.invalid", aal="aal1")
    with Session(state.engine) as session, session.begin():
        database.register_movies(session, [1, 2])
        database.save_rating(session, 207, 1, 1.5)
    def storage():
        with Session(state.engine) as session, session.begin(): yield session
    @state.app.get("/private/{user_id}")
    def read(user_id: int, principal=Depends(state.dependency), session=Depends(storage, scope="function")):
        return access.read_ratings(session, principal, user_id)
    @state.app.put("/private/{user_id}/{movie_id}")
    def put(user_id: int, movie_id: int, body: RatingRequest, principal=Depends(state.dependency),
            session=Depends(storage, scope="function")):
        return access.put_rating(session, principal, user_id, movie_id, body.rating)
    @state.app.delete("/private/{user_id}/{movie_id}")
    def remove(user_id: int, movie_id: int, principal=Depends(state.dependency), session=Depends(storage, scope="function")):
        access.delete_rating(session, principal, user_id, movie_id)
        return {"ok": True}
    return state


def test_owner_crud_and_mass_assignment_cannot_change_owner(resources):
    state = resources
    headers = {"Authorization": "Bearer " + state.token(), "X-User-Id": "207"}
    with TestClient(state.app) as client:
        assert client.get("/private/104?user_id=207", headers=headers).json() == {}
        for value in (3.0, 4.5):
            body = dict(rating=value, user_id=207, owner_id=207, visibility="public", role="admin")
            assert client.put("/private/104/1", json=body, headers=headers).json() == value
        assert client.get("/private/104", headers=headers).json() == {"1": 4.5}
        assert client.delete("/private/104/1", headers=headers).status_code == 200
        assert client.delete("/private/104/1", headers=headers).status_code == 404
        assert client.get("/private/104", headers=headers).json() == {}
    with Session(state.engine) as session:
        assert database.get_user_profile(session, 207) == {1: 1.5}


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_other_owner_and_missing_profile_are_indistinguishable(resources, method, caplog):
    state = resources
    token = state.token()
    with TestClient(state.app) as client, caplog.at_level(logging.DEBUG):
        for target in (207, 999):
            path = f"/private/{target}" + ("/1" if method != "get" else "")
            kwargs = {"json": {"rating": 5, "user_id": 207}} if method == "put" else {}
            result = client.request(method, path, headers={"Authorization": "Bearer " + token}, **kwargs)
            assert result.status_code == 404 and result.json() == {"detail": "Resource unavailable"}
            assert result.headers["cache-control"] == "no-store"
    no_secrets(result.text + caplog.text, [token, state.subject, "offline@example.invalid"])
    with Session(state.engine) as session:
        assert database.get_user_profile(session, 207) == {1: 1.5}


def test_unverified_or_unbound_principals_are_not_owner_proofs(resources):
    state = resources
    other = SupabaseAuthContext(user_id=207, subject=state.subjects[0], email=state.principal.email, aal="aal1")
    unknown = SupabaseAuthContext(user_id=104, subject=uuid4(), email=state.principal.email, aal="aal2")
    with Session(state.engine) as session:
        for caller in (None, 104, {"user_id": 104}, other, unknown):
            with pytest.raises(HTTPException) as error: access.read_ratings(session, caller, 104)
            assert error.value.status_code == 404
    with TestClient(state.app) as client:
        assert client.get("/private/104", headers={"X-User-Id": "104"}).status_code == 401


def test_pagination_and_cached_orm_objects_do_not_change_binding(resources):
    state = resources
    with Session(state.engine) as session, session.begin():
        assert access.require_profile_owner(session, state.principal, 104) == 104
        access.put_rating(session, state.principal, 104, 1, 3)
        access.put_rating(session, state.principal, 104, 2, 4)
        assert access.read_ratings(session, state.principal, 104, limit=1) == {1: 3}
        assert access.read_ratings(session, state.principal, 104, after=1) == {2: 4}
        assert access.read_ratings(session, state.principal, 104, after=2) == {}
        cached = session.get(UserIdentity, 104)
        cached.supabase_subject = uuid4()  # Must not flush caller-owned pending changes.
        assert access.read_ratings(session, state.principal, 104) == {1: 3, 2: 4}
        session.rollback()


def test_revocation_between_guard_and_mutation_fails_closed(resources, monkeypatch):
    state = resources
    original = database.enforce_rating_quota
    def revoke(session, *args):
        with Session(state.engine) as other, other.begin():
            other.execute(delete(UserIdentity).where(UserIdentity.user_id == 104))
        original(session, *args)
    monkeypatch.setattr(database, "enforce_rating_quota", revoke)
    with pytest.raises(HTTPException) as error:
        with Session(state.engine) as session, session.begin():
            access.put_rating(session, state.principal, 104, 1, 5)
    assert error.value.status_code == 404
    with Session(state.engine) as session:
        assert session.get(UserIdentity, 104) is None
        assert session.get(UserRating, (104, 1)) is None


@pytest.mark.parametrize("operation", ["profile", "read", "put", "delete"])
def test_storage_outages_are_generic_without_unscoped_fallback(resources, monkeypatch, operation, caplog):
    state = resources
    with Session(state.engine) as session:
        def broken(*args, **kwargs): raise OperationalError("private SQL", {}, Exception("private diagnostic"))
        monkeypatch.setattr(session, "execute", broken)
        monkeypatch.setattr(session, "scalar", broken)
        actions = {"profile": lambda: access.require_profile_owner(session, state.principal, 104),
                   "read": lambda: access.read_ratings(session, state.principal, 104),
                   "put": lambda: access.put_rating(session, state.principal, 104, 1, 5),
                   "delete": lambda: access.delete_rating(session, state.principal, 104, 1)}
        with caplog.at_level(logging.DEBUG), pytest.raises(HTTPException) as error: actions[operation]()
    assert error.value.status_code == 503 and error.value.detail == "Resource service unavailable"
    no_secrets(str(error.value) + caplog.text, [state.subject, state.principal.email, "private SQL", "private diagnostic"])


def test_concurrent_upserts_keep_each_owner_in_the_composite_key(resources):
    state = resources
    callers = [state.principal, SupabaseAuthContext(user_id=207, subject=state.subjects[1], email="other@example.invalid", aal="aal1")]
    def write(caller):
        with Session(state.engine) as session, session.begin():
            for value in (3.0, 4.0):
                access.put_rating(session, caller, caller.user_id, 1, value)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(write, callers))
    with Session(state.engine) as session:
        assert access.read_ratings(session, callers[0], 104) == {1: 4}
        assert access.read_ratings(session, callers[1], 207) == {1: 4}
