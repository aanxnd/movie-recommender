"""Pending-deletion privacy, including previously issued sharing capabilities."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

from fastapi import HTTPException
import pytest
from sqlalchemy.orm import Session

from app import account_settings, database, group_authorization as groups, resource_authorization as access, security
from app.deletion_store import metadata
from app.models import Credential, GroupInvitation, UserIdentity
from app.provisioning import inspect_profile, provision_profile
from app.provisioning_principal import ProfileInput, ProvisioningPrincipal
from app.supabase_auth import SupabaseAuthContext
from test_deletion_store import deletion, identity_engine, pg_engine, requested


def native(p, uid):
    return SupabaseAuthContext(uid, p.subject, 'synthetic@example.invalid', p.aal)


def resource_sessions(engine):
    return Session(engine, info={'lifecycle_enabled': True})


def test_queue_commit_revokes_capabilities_without_erasing_ratings(deletion):
    store, p, uid, peer, engine = deletion
    with Session(engine) as s, s.begin():
        s.add(Credential(user_id=uid, token_hash='f'*64, expires_at=2**40))
    requested(deletion)
    with Session(engine) as s:
        assert s.get(GroupInvitation, uid) is None and s.get(Credential, uid) is None
        assert database.get_user_profile(s, uid) == {10: 4}
        assert database.get_user_profile(s, peer) == {10: 2}


def test_previously_authenticated_request_cannot_reissue_sharing_or_write_after_intent(deletion):
    store, p, uid, _, engine = deletion
    principal = native(p, uid)
    requested(deletion)
    for operation in [lambda s: groups.issue_invitation(s, principal, uid),
                      lambda s: access.put_rating(s, principal, uid, 10, 1),
                      lambda s: access.read_ratings(s, principal, uid)]:
        with pytest.raises(HTTPException), resource_sessions(engine) as s, s.begin(): operation(s)
    proof = ProvisioningPrincipal(p.subject, p.session_id, p.expires_at, p.aal)
    for operation in [lambda: inspect_profile(lambda: resource_sessions(engine), proof),
                      lambda: provision_profile(lambda: resource_sessions(engine), proof, ProfileInput(username='Reclaim')),
                      lambda: account_settings.profile_settings(lambda: resource_sessions(engine), proof)]:
        with pytest.raises(HTTPException): operation()


def test_group_query_excludes_pending_peer_even_with_a_residual_valid_invitation(deletion):
    store, p, uid, peer, engine = deletion
    peer_subject = uuid4()
    with Session(engine) as s, s.begin():
        s.add(UserIdentity(user_id=peer, supabase_subject=peer_subject, username='Peer'))
        token, _ = groups.issue_invitation(s, native(p, uid), uid)
    requested(deletion)
    # Simulate a residual capability from an old in-flight revision; guard must not trust it.
    with Session(engine) as s, s.begin():
        s.add(GroupInvitation(user_id=uid, token_hash=security.token_hash(token), expires_at=2**40))
    peer_principal = SupabaseAuthContext(peer, peer_subject, 'peer@example.invalid', 'aal1')
    with pytest.raises(HTTPException), resource_sessions(engine) as s, s.begin():
        groups.combined_group_profile(s, peer_principal, [peer, uid], {uid: token})


def test_queue_waits_for_inflight_invitation_then_revokes_it(deletion):
    store, p, uid, _, engine = deletion
    entered, release, queued = Event(), Event(), Event()
    def invite():
        with resource_sessions(engine) as s, s.begin():
            groups.issue_invitation(s, native(p, uid), uid)
            entered.set(); assert release.wait(5)
    def enqueue():
        queued.set(); return requested(deletion)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(invite); assert entered.wait(5)
        second = pool.submit(enqueue); assert queued.wait(5)
        release.set(); first.result(timeout=5); second.result(timeout=5)
    with Session(engine) as s: assert s.get(GroupInvitation, uid) is None


def test_lost_lifecycle_storage_cannot_authorize_an_already_resolved_principal(deletion):
    _, p, uid, _, engine = deletion
    metadata.drop_all(engine)  # Disposable fixture only.
    with pytest.raises(HTTPException) as error, resource_sessions(engine) as s, s.begin():
        access.read_ratings(s, native(p, uid), uid)
    assert error.value.status_code == 503
