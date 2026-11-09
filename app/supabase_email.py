"""Dormant provider email-confirmation evidence; never active-account/session/MFA proof."""
from dataclasses import dataclass
from datetime import datetime, timezone
from http.client import HTTPException
import json
import re
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import UUID

from app.supabase_jwt import InvalidAccessToken, SigningKeysUnavailable, SupabaseTokenVerifier


class EmailConfirmationDenied(ValueError):
    """Unconfirmed, conflicting or rejected evidence; no account details in errors."""


class EmailEvidenceUnavailable(RuntimeError):
    """Provider evidence unavailable: never fall back to JWT email/metadata."""


@dataclass(frozen=True, slots=True, repr=False)
class ProviderEmailConfirmation:
    """Point-in-time provider marker only; configuration/admin provenance still matters."""

    subject: UUID
    confirmed_at: datetime
    observed_at: datetime


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _read_user(url, publishable_key, token):
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    request = Request(url, headers={"apikey": publishable_key, "Authorization": "Bearer " + token,
                                   "Accept": "application/json", "Cache-Control": "no-store"})
    with opener.open(request, timeout=3) as response:
        if response.status != 200:
            raise ValueError("Provider response rejected")
        body = response.read(65537)
    if len(body) > 65536:
        raise ValueError("Provider response too large")
    return body


class ProviderEmailPolicy:
    """Configure once on the trusted server; call in a sync worker, never an async loop.

    No import/construction I/O, user cache, environment loading or privileged key.
    Confirm Email and historic provisioning must be audited before access integration.
    """

    def __init__(self, *, project_url: str, audience: str, publishable_key: str):
        if not isinstance(publishable_key, str) or not re.fullmatch(r"sb_publishable_[A-Za-z0-9_-]{1,256}", publishable_key):
            raise ValueError("Expected a public publishable API key")
        self._verifier = SupabaseTokenVerifier(project_url, audience=audience)
        self._url, self._key = self._verifier.issuer + "/user", publishable_key

    def check(self, token: str) -> ProviderEmailConfirmation:
        """Fetch fresh Auth user data after JWT verification; accept no caller claims/booleans.

        Only id, email and email_confirmed_at are evidence. Metadata, confirmed_at
        (which may refer to phone confirmation), JWT email and aal confer no proof.
        """
        try:
            subject = self._verifier.verify(token)
            user = json.loads(_read_user(self._url, self._key, token))
            observed = datetime.now(timezone.utc)
            if not isinstance(user, dict) or user.get("id") != str(subject):
                raise EmailConfirmationDenied
            email, confirmed = user.get("email"), user.get("email_confirmed_at")
            if (not isinstance(email, str) or len(email) > 320 or not re.fullmatch(r"[^@\s]+@[^@\s]+", email)
                    or not isinstance(confirmed, str) or not 1 <= len(confirmed) <= 64):
                raise EmailConfirmationDenied
            try:
                timestamp = datetime.fromisoformat(confirmed)
            except ValueError:
                raise EmailConfirmationDenied from None
            if timestamp.tzinfo is None or timestamp > observed:
                raise EmailConfirmationDenied
            return ProviderEmailConfirmation(subject=subject, confirmed_at=timestamp, observed_at=observed)
        except (InvalidAccessToken, EmailConfirmationDenied):
            raise EmailConfirmationDenied("Email confirmation evidence rejected") from None
        except HTTPError as error:
            status = error.code
            error.close()
            if status in {401, 403, 404}:
                raise EmailConfirmationDenied("Email confirmation evidence rejected") from None
            raise EmailEvidenceUnavailable("Email confirmation evidence unavailable") from None
        except (OSError, HTTPException, ValueError, TypeError, RecursionError, SigningKeysUnavailable):
            raise EmailEvidenceUnavailable("Email confirmation evidence unavailable") from None
