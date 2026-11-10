"""Dormant standard Supabase policy; authentication evidence is not resource authorization."""
from datetime import datetime, timezone
from http.client import HTTPException
import json
import re
from urllib.error import HTTPError
from uuid import UUID

from app.supabase_email import (EmailConfirmationDenied, ProviderEmailConfirmation,
                                _confirmed_current_email, _read_user)
from app.supabase_jwt import (InvalidAccessToken, SigningKeysUnavailable, SupabaseTokenVerifier,
                              VerifiedTokenClaims, _unique_object)


class AccessDenied(ValueError):
    """Fixed public denial, without account or provider diagnostics."""


class AccessUnavailable(RuntimeError):
    """No provider/key evidence; no fallback."""


class SupabaseAccessPolicy:
    """Server-configured, synchronous worker only; construction performs no I/O.

    Trust native provider email confirmation, not independent mailbox provenance.
    Accept standard JWT lifetime semantics: this does not prove a live session row,
    immediate logout/ban revocation, or recent MFA. Never use its result as ownership.
    """

    def __init__(self, *, project_url: str, audience: str, publishable_key: str):
        if not isinstance(publishable_key, str) or not re.fullmatch(r"sb_publishable_[A-Za-z0-9_-]{1,256}", publishable_key):
            raise ValueError("Expected a public publishable API key")
        self._verifier = SupabaseTokenVerifier(project_url, audience=audience)
        self._url, self._key = self._verifier.issuer + "/user", publishable_key

    def check(self, token: str) -> VerifiedTokenClaims:
        """Compatibility entry point; reuse the same checks, discarding email evidence."""
        return self.check_with_email(token)[0]

    def check_with_email(self, token: str) -> tuple[VerifiedTokenClaims, ProviderEmailConfirmation]:
        """One signature verification and one fresh user read; no resource access grant."""
        try:
            claims = self._verifier.verify_claims(token)
            user = json.loads(_read_user(self._url, self._key, token), object_pairs_hook=_unique_object)
            now = datetime.now(timezone.utc)
            if (not isinstance(user, dict) or user.get("id") != str(claims.subject)
                    or user.get("aud") != "authenticated" or user.get("role") != "authenticated"
                    or user.get("is_anonymous") is not False or user.get("deleted_at") is not None):
                raise AccessDenied
            email = _confirmed_current_email(user, claims.subject, now)
            if user.get("banned_until") is not None:
                if self._timestamp(user["banned_until"]) > now:
                    raise AccessDenied
            # Require explicit evidence: SDK null/omission normalization is not a
            # server guarantee that this account has no verified factor.
            factors = user.get("factors")
            if not isinstance(factors, list) or len(factors) > 10:
                raise AccessDenied
            verified = False
            seen = set()
            for factor in factors:
                if not isinstance(factor, dict):
                    raise AccessDenied
                identifier = UUID(factor["id"])
                if (not identifier.int or str(identifier) != factor["id"] or identifier in seen
                        or factor.get("factor_type") != "totp"
                        or factor.get("status") not in {"verified", "unverified"}):
                    raise AccessDenied
                seen.add(identifier)
                verified |= factor["status"] == "verified"
            if (verified and claims.aal != "aal2") or claims.expires_at <= now.timestamp():
                raise AccessDenied
            return claims, email
        except (AccessDenied, InvalidAccessToken, EmailConfirmationDenied):
            raise AccessDenied("Authentication evidence rejected") from None
        except HTTPError as error:
            status = error.code
            error.close()
            if status in {401, 403, 404}:
                raise AccessDenied("Authentication evidence rejected") from None
            raise AccessUnavailable("Authentication evidence unavailable") from None
        except (OSError, HTTPException, ValueError, TypeError, KeyError, AttributeError,
                RecursionError, SigningKeysUnavailable):
            raise AccessUnavailable("Authentication evidence unavailable") from None

    @staticmethod
    def _timestamp(value):
        if not isinstance(value, str) or not 1 <= len(value) <= 64:
            raise AccessDenied
        value = datetime.fromisoformat(value)
        if value.tzinfo is None:
            raise AccessDenied
        return value
