"""Dormant evidence composition; no resource access, current AAL or recent-MFA grant."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from time import monotonic
from typing import Literal, Protocol
from urllib.error import HTTPError
from uuid import UUID, uuid4

from app.supabase_email import _read_user
from app.supabase_jwt import InvalidAccessToken, SupabaseTokenVerifier, VerifiedTokenClaims, _unique_object


class AuthenticationEvidenceDenied(ValueError):
    """Map all rejected/unknown evidence to a fixed denial, never provider details."""


class AuthenticationEvidenceUnavailable(RuntimeError):
    """Required evidence unavailable; never use stale evidence or another credential."""


@dataclass(frozen=True, slots=True, repr=False)
class MailboxChallenge:
    """Internal trusted-workflow attestation, NOT a Supabase user/JWT field.

    Reader must invalidate on every address change, including A -> B -> A.
    Confirmation time is an extra binding, never the source of mailbox proof.
    """

    issuer: str
    subject: UUID
    email: str
    confirmed_at: datetime
    verified_at: datetime
    valid_until: datetime


@dataclass(frozen=True, slots=True, repr=False)
class LiveAccountSession:
    """Internal fresh authoritative read, NOT fields invented for GET /user.

    'present' requires ownership/existence and applicable revocation/expiry checks;
    'enabled' requires explicit account ban/deletion/disable checks.
    """

    issuer: str
    subject: UUID
    session_id: UUID
    nonce: UUID
    observed_at: datetime
    email: str
    confirmed_at: datetime
    account_state: Literal["enabled", "deleted", "banned", "disabled", "unknown"]
    session_state: Literal["present", "revoked", "missing", "unknown"]


class MailboxSource(Protocol):
    """Server-only trusted challenge ledger; unknown/unproven/revoked records -> None.

    Must establish genuine challenge origin, protect writes, enforce expiry and
    invalidate ALL prior address evidence on changes. Never wrap client JSON.
    """

    def read(self, *, issuer: str, subject: UUID, email: str,
             confirmed_at: datetime) -> MailboxChallenge | None: ...


class LiveStateSource(Protocol):
    """Server-only authoritative same-project account/session reader, no cache.

    Must read afresh for each nonce; bind BOTH subject and session, not JWT claims
    or GET /user alone. Unknown/missing binding -> None; outages must raise.
    No supported concrete implementation is configured by this PR.
    """

    def read(self, *, issuer: str, subject: UUID, session_id: UUID,
             nonce: UUID) -> LiveAccountSession | None: ...


@dataclass(frozen=True, slots=True, repr=False)
class VerifiedAuthenticationEvidence:
    """Conditional point-in-time evidence only, not local ownership or authorization."""

    claims: VerifiedTokenClaims
    observed_at: datetime


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    return type(value) is datetime and value.utcoffset() is not None


def _provider_time(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise AuthenticationEvidenceDenied
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise AuthenticationEvidenceDenied from None
    if not _aware(parsed):
        raise AuthenticationEvidenceDenied
    return parsed


class AuthenticationEvidencePolicy:
    """Construct only with trusted server adapters; check accepts ONLY a raw JWT.

    Missing adapters deny; types/records cannot establish their own provenance.
    No import/construction I/O, database mutation, positive cache or route wiring.
    """

    def __init__(self, *, project_url: str, audience: str, publishable_key: str,
                 mailbox: MailboxSource | None = None, live_state: LiveStateSource | None = None):
        if not isinstance(publishable_key, str) or not re.fullmatch(r"sb_publishable_[A-Za-z0-9_-]{1,256}", publishable_key):
            raise ValueError("Expected a public publishable API key")
        self._verifier = SupabaseTokenVerifier(project_url, audience=audience)
        self._url, self._key = self._verifier.issuer + "/user", publishable_key
        self._mailbox, self._live = mailbox, live_state

    def check(self, token: str) -> VerifiedAuthenticationEvidence:
        try:
            started, tick = _now(), monotonic()
            claims = self._verifier.verify_claims(token)
            if self._mailbox is None or self._live is None:
                raise AuthenticationEvidenceDenied
            body = _read_user(self._url, self._key, token)
            if type(body) is not bytes or len(body) > 65536:
                raise AuthenticationEvidenceUnavailable
            user = json.loads(body, object_pairs_hook=_unique_object)
            if (not isinstance(user, dict) or user.get("id") != str(claims.subject)
                    or user.get("aud") != self._verifier.audience or user.get("role") != "authenticated"):
                raise AuthenticationEvidenceDenied
            email = user.get("email")
            if not isinstance(email, str) or len(email) > 320 or not re.fullmatch(r"[^@\s]+@[^@\s]+", email):
                raise AuthenticationEvidenceDenied
            confirmed = _provider_time(user.get("email_confirmed_at"))
            if (confirmed > _now() or user.get("deleted_at") is not None
                    or user.get("is_anonymous") is not False):
                raise AuthenticationEvidenceDenied
            if user.get("banned_until") is not None and _provider_time(user["banned_until"]) > _now():
                raise AuthenticationEvidenceDenied
            nonce = uuid4()
            live = self._live.read(issuer=self._verifier.issuer, subject=claims.subject,
                                   session_id=claims.session_id, nonce=nonce)
            if (type(live) is not LiveAccountSession or live.issuer != self._verifier.issuer
                    or type(live.subject) is not UUID or type(live.session_id) is not UUID or type(live.nonce) is not UUID
                    or live.subject != claims.subject or live.session_id != claims.session_id or live.nonce != nonce
                    or live.account_state != "enabled" or live.session_state != "present"
                    or type(live.email) is not str or live.email != email or not _aware(live.confirmed_at)
                    or live.confirmed_at != confirmed
                    or not _aware(live.observed_at) or not started <= live.observed_at <= _now()):
                raise AuthenticationEvidenceDenied
            proof = self._mailbox.read(issuer=self._verifier.issuer, subject=claims.subject,
                                       email=email, confirmed_at=confirmed)
            now = _now()
            if (type(proof) is not MailboxChallenge or proof.issuer != self._verifier.issuer
                    or type(proof.subject) is not UUID or proof.subject != claims.subject
                    or type(proof.email) is not str or proof.email != email or not _aware(proof.confirmed_at)
                    or proof.confirmed_at != confirmed
                    or not _aware(proof.verified_at) or not _aware(proof.valid_until)
                    or not confirmed <= proof.verified_at <= now < proof.valid_until):
                raise AuthenticationEvidenceDenied
            # Reject late evidence/token expiry; this is NOT cancellation of blocked I/O.
            if now.timestamp() >= claims.expires_at or monotonic() - tick > 3:
                raise AuthenticationEvidenceUnavailable
            return VerifiedAuthenticationEvidence(claims, now)
        except (InvalidAccessToken, AuthenticationEvidenceDenied):
            raise AuthenticationEvidenceDenied("Authentication evidence rejected") from None
        except HTTPError as error:
            try:
                status = error.code
                error.close()
            except Exception:
                raise AuthenticationEvidenceUnavailable("Authentication evidence unavailable") from None
            if status in {401, 403, 404}:
                raise AuthenticationEvidenceDenied("Authentication evidence rejected") from None
            raise AuthenticationEvidenceUnavailable("Authentication evidence unavailable") from None
        except Exception:
            # Provider/adapter/parse failures are an external trust boundary; redact all diagnostics.
            raise AuthenticationEvidenceUnavailable("Authentication evidence unavailable") from None
