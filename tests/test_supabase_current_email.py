"""Upstream-shaped snapshots, not hosted verification of email-change transitions."""
from dataclasses import FrozenInstanceError
import json
import logging
from uuid import uuid4

import pytest

from app import supabase_email as email_policy
from app import supabase_policy as access_policy
from test_supabase_email import provider, jwt_setup
from test_supabase_policy import account, evidence
from test_validation_redaction import no_secrets


def test_current_address_follows_fresh_provider_state_not_old_jwt_or_pending(provider):
    token = provider.sign({"email": "stale@example.invalid"})
    original = provider.body["email"]
    marker = provider.body["email_confirmed_at"]
    first = provider.client.check(token)
    provider.body.update(new_email="next@example.invalid", email_change_sent_at=marker)
    pending = provider.client.check(token)
    # Secure-change first confirmation does not alter these public fields.
    partial = provider.client.check(token)
    assert first.email == pending.email == partial.email == original
    assert not hasattr(partial, "new_email") and not hasattr(partial, "change_complete")
    provider.body.update(email="next@example.invalid")
    del provider.body["new_email"]  # Go omitempty after successful completion
    complete = provider.client.check(token)
    assert complete.email == "next@example.invalid"
    assert complete.confirmed_at == first.confirmed_at  # Native timestamp can be retained.
    # Fresh provider state, not address history, also governs a later return to A.
    provider.body.update(email=original, new_email="")
    assert provider.client.check(token).email == original
    assert len(provider.requests) == 5
    with pytest.raises(FrozenInstanceError): complete.email = original


@pytest.mark.parametrize("change", [
    {"email": "bad@@example.invalid"}, {"email": "a\x00@example.invalid"},
    {"email": "a\n@example.invalid"}, {"email": "a" * 321 + "@b"},
    {"new_email": None}, {"new_email": True}, {"new_email": []},
    {"new_email": "invalid"}, {"new_email": "owner@example.invalid"},
    {"email_change_sent_at": None}, {"email_change_sent_at": True},
    {"email_change_sent_at": "2026-01-01"}, {"email_change_sent_at": "invalid"},
    {"email_change_sent_at": "2999-01-01T00:00:00Z"},
    {"email_confirmed_at": None, "new_email": "next@example.invalid"},
])
def test_malformed_or_inconsistent_email_evidence_is_rejected(provider, change, caplog):
    provider.body.update(change)
    token = provider.sign({"email": "next@example.invalid", "email_verified": True})
    with caplog.at_level(logging.DEBUG), pytest.raises(email_policy.EmailConfirmationDenied) as error:
        provider.client.check(token)
    assert str(error.value) == "Email confirmation evidence rejected"
    no_secrets(str(error.value) + caplog.text, [token, "next@example.invalid", "owner@example.invalid"])


def test_duplicate_email_fields_cannot_select_an_attacker_address(provider):
    body = json.dumps(provider.body)
    provider.body = (body[:-1] + ',"email":"attacker@example.invalid"}').encode()
    with pytest.raises(email_policy.EmailEvidenceUnavailable): provider.client.check(provider.sign())


def test_same_email_does_not_allow_cross_account_substitution(provider):
    provider.body["id"] = str(uuid4())
    with pytest.raises(email_policy.EmailConfirmationDenied): provider.client.check(provider.sign())


@pytest.mark.parametrize("failure", [TimeoutError("private"), OSError("private")])
def test_previous_current_address_never_becomes_an_outage_fallback(provider, failure):
    token = provider.sign()
    result = provider.client.check(token)
    no_secrets(repr(result), [result.email, str(result.subject)])
    provider.failure = failure
    with pytest.raises(email_policy.EmailEvidenceUnavailable): provider.client.check(token)
    assert len(provider.requests) == 2


def test_old_pending_snapshot_still_uses_current_email_and_does_not_redeem_links(provider):
    # Expiry/failure/replay need not clear pending fields. No transition is inferred
    # from this snapshot, and these reads cannot consume a token or cancel a request.
    provider.body.update(new_email="next@example.invalid", email_change_sent_at="2020-01-01T00:00:00Z")
    token = provider.sign()
    assert provider.client.check(token).email == "owner@example.invalid"
    assert provider.client.check(token).email == "owner@example.invalid"
    assert all(r.get_method() == "GET" and r.data is None for r in provider.requests)


@pytest.mark.parametrize("changed", [False, True])
@pytest.mark.parametrize("verified,aal,allowed", [(False, "aal1", True), (True, "aal1", False),
                                                 (True, "aal2", True)])
def test_pending_or_completed_change_preserves_existing_mfa_boundary(account, changed, verified, aal, allowed):
    e, client, user, calls = account
    user.update(new_email="next@example.invalid", email_change_sent_at="2026-01-01T00:00:00Z")
    if changed:
        user.update(email="next@example.invalid", new_email="")
    user["factors"] = [dict(id=str(uuid4()), factor_type="totp", status="verified" if verified else "unverified")]
    token = e.sign({"aal": aal, "email": "stale@example.invalid"})
    if allowed:
        assert client.check(token).subject == e.subject
    else:
        with pytest.raises(access_policy.AccessDenied): client.check(token)
    assert len(calls) == 1


@pytest.mark.parametrize("change", [{"new_email": None}, {"email_confirmed_at": None},
                                    {"email": "a\x00@example.invalid"}, {"email_change_sent_at": False}])
def test_access_policy_reuses_the_same_email_validation(account, change):
    e, client, user, _ = account
    user.update(change)
    with pytest.raises(access_policy.AccessDenied, match="^Authentication evidence rejected$"):
        client.check(e.sign())
