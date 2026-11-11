"""Existing capability semantics with real isolated storage; no invented memberships."""
import logging

from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import group_authorization as groups, resource_authorization as access
from app.models import GroupInvitation, UserIdentity
from app.schemas import GroupRequest
from app.supabase_auth import SupabaseAuthContext
from test_resource_authorization import resources, environment, engine, linked, pg_engine, evidence
from test_validation_redaction import no_secrets


@pytest.fixture
def shared(resources):
    state = resources
    state.other = SupabaseAuthContext(user_id=207, subject=state.subjects[1], email="other@example.invalid", aal="aal1")
    with Session(state.engine) as session, session.begin():
        access.put_rating(session, state.principal, 104, 1, 4.5)
        token, _ = groups.issue_invitation(session, state.other, 207)
    state.capabilities = lambda: {207: token}  # Keep credentials out of fixture reprs.
    return state


def test_owner_controls_rotation_revocation_and_capability_is_not_ownership(shared):
    state = shared
    with Session(state.engine) as session, session.begin():
        assert groups.combined_group_profile(session, state.principal, [104, 207], state.capabilities()) == {1: 3}
        for action in (lambda: groups.issue_invitation(session, state.principal, 207),
                       lambda: groups.revoke_invitation(session, state.principal, 207),
                       lambda: access.read_ratings(session, state.principal, 207),
                       lambda: access.put_rating(session, state.principal, 207, 1, 5),
                       lambda: access.delete_rating(session, state.principal, 207, 1)):
            with pytest.raises(HTTPException) as error: action()
            assert error.value.status_code == 404
        groups.issue_invitation(session, state.other, 207)
        with pytest.raises(HTTPException):
            groups.combined_group_profile(session, state.principal, [104, 207], state.capabilities())
        groups.revoke_invitation(session, state.other, 207)
        assert session.get(GroupInvitation, 207) is None


@pytest.mark.parametrize("kind", ["missing", "forged", "substitution", "extra", "duplicate", "unknown",
                                  "not-caller", "role", "format", "oversized", "bool"])
def test_group_membership_assertions_cannot_substitute_for_explicit_consent(shared, kind):
    state = shared
    users, tokens = [104, 207], state.capabilities()
    if kind == "missing": tokens = {}
    if kind == "forged": tokens[207] = "x" * 43
    if kind == "substitution": users, tokens = [104, 308], {308: tokens[207]}
    if kind == "extra": tokens[104] = tokens[207]
    if kind == "duplicate": users = [104, 104]
    if kind == "unknown": users, tokens = [104, 999], {999: tokens[207]}
    if kind == "not-caller": users = [207, 308]
    if kind == "role": tokens[207] = {"role": "admin"}
    if kind == "format": tokens[207] = "invalid"
    if kind == "oversized": users = [104, 207, 308, 409, 510, 611]
    if kind == "bool": users = [True, 207]
    with Session(state.engine) as session, pytest.raises(HTTPException) as error:
        groups.combined_group_profile(session, state.principal, users, tokens)
    assert error.value.status_code == 404 and error.value.detail == "Resource unavailable"


@pytest.mark.parametrize("change", ["expired", "deleted", "rotated", "unbound"])
def test_removed_or_inactive_capabilities_ignore_stale_orm_state(shared, change):
    state = shared
    with Session(state.engine) as reader:
        cached = reader.get(GroupInvitation, 207)
        with Session(state.engine) as writer, writer.begin():
            if change == "expired": writer.get(GroupInvitation, 207).expires_at = 1
            if change == "deleted": groups.revoke_invitation(writer, state.other, 207)
            if change == "rotated": groups.issue_invitation(writer, state.other, 207)
            if change == "unbound": writer.execute(delete(UserIdentity).where(UserIdentity.user_id == 104))
        assert cached is not None  # Loading an old ORM instance grants nothing.
        with pytest.raises(HTTPException) as error:
            groups.combined_group_profile(reader, state.principal, [104, 207], state.capabilities())
        assert error.value.status_code == 404


def test_revocation_between_clock_read_and_profile_query_is_not_bypassed(shared, monkeypatch):
    state = shared
    original = groups.limits.database_now
    def revoke(session):
        now = original(session)
        with Session(state.engine) as other, other.begin():
            groups.revoke_invitation(other, state.other, 207)
        return now
    monkeypatch.setattr(groups.limits, "database_now", revoke)
    with Session(state.engine) as session, pytest.raises(HTTPException):
        groups.combined_group_profile(session, state.principal, [104, 207], state.capabilities())


def test_expiry_during_read_does_not_return_a_combined_profile(shared, monkeypatch):
    state = shared
    with Session(state.engine) as session:
        now = groups.limits.database_now(session)
        ticks = iter([now, now + 601])
        monkeypatch.setattr(groups.limits, "database_now", lambda _: next(ticks))
        with pytest.raises(HTTPException):
            groups.combined_group_profile(session, state.principal, [104, 207], state.capabilities())


@pytest.mark.parametrize("limit", ["MAX_PROFILE_RATINGS", "MAX_GROUP_RATINGS"])
def test_group_computation_preserves_existing_workload_bounds(shared, monkeypatch, limit):
    state = shared
    monkeypatch.setattr(groups.limits, limit, 0)
    with Session(state.engine) as session, pytest.raises(HTTPException):
        groups.combined_group_profile(session, state.principal, [104, 207], state.capabilities())


@pytest.mark.parametrize("operation", ["issue", "revoke", "compute"])
def test_storage_errors_fail_closed_without_exposing_capabilities(shared, monkeypatch, operation, caplog):
    state = shared
    with Session(state.engine) as session:
        def broken(*a, **kw): raise OperationalError("private SQL", {}, Exception("private diagnostic"))
        monkeypatch.setattr(session, "execute", broken)
        monkeypatch.setattr(session, "scalar", broken)
        actions = {"issue": lambda: groups.issue_invitation(session, state.principal, 104),
                   "revoke": lambda: groups.revoke_invitation(session, state.principal, 104),
                   "compute": lambda: groups.combined_group_profile(session, state.principal, [104, 207], state.capabilities())}
        with caplog.at_level(logging.DEBUG), pytest.raises(HTTPException) as error: actions[operation]()
    assert error.value.status_code == 503 and error.value.detail == "Resource service unavailable"
    no_secrets(str(error.value) + caplog.text, [state.capabilities()[207], state.subject, "private SQL", "private diagnostic"])


def test_only_authenticated_caller_can_use_capability_for_test_only_computation(shared):
    state = shared
    @state.app.post("/shared-probe")
    def compute(body: GroupRequest, principal=Depends(state.dependency)):
        with Session(state.engine) as session, session.begin():
            groups.combined_group_profile(session, principal, body.user_ids, body.invitations)
        return {"ready": True}  # Never serialize private/combined recommendation inputs.
    body = dict(user_ids=[104, 207], invitations=state.capabilities(), role="admin", visibility="public", owner_id=207)
    with TestClient(state.app) as client:
        assert client.post("/shared-probe", json=body).status_code == 401
        headers = {"Authorization": "Bearer " + state.capabilities()[207]}
        assert client.post("/shared-probe", json=body, headers=headers).status_code == 401
        headers = {"Authorization": "Bearer " + state.token(), "X-Group-Role": "admin"}
        result = client.post("/shared-probe", json=body, headers=headers)
        assert result.status_code == 200 and result.json() == {"ready": True}
