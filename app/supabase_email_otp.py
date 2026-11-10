"""Dormant supported native email-OTP redemption; no route activation."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from time import monotonic
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import UUID

from app.supabase_email import _NoRedirect, _read_user
from app.supabase_jwt import InvalidAccessToken, SupabaseTokenVerifier, _unique_object


class EmailOtpDenied(ValueError):
    """Fixed denial; never expose code, token, email or provider diagnostics."""


class EmailOtpUnavailable(RuntimeError):
    """Indeterminate redemption; do not retry a potentially consumed OTP automatically."""


@dataclass(frozen=True, slots=True, repr=False)
class EmailOtpRedemption:
    """Native credential was accepted; no resource authorization is conferred.

    Never use as MFA, session-liveness or account-linking proof.
    No bearer credentials retained; standard signup/recovery use the Supabase SDK.
    """

    issuer: str
    subject: UUID
    session_id: UUID
    email: str
    confirmed_at: datetime
    redeemed_at: datetime


def _now():
    return datetime.now(timezone.utc)


def _post_verify(url, key, email, code):
    # Supported Auth API, not a caller URL. OTP is JSON, never a URL/log parameter.
    request = Request(url, data=json.dumps({"email": email, "token": code, "type": "email"}).encode(),
        headers={"apikey": key, "Content-Type": "application/json", "Accept": "application/json",
                 "Cache-Control": "no-store"}, method="POST")
    with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=3) as response:
        if response.status != 200:
            raise EmailOtpUnavailable
        return response.read(65537)


def _json(body):
    if type(body) is not bytes or len(body) > 65536:
        raise EmailOtpUnavailable
    value = json.loads(body, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise EmailOtpDenied
    return value


def _user(value, subject, audience, *, confirmed):
    if (value.get("id") != str(subject) or value.get("aud") != audience
            or value.get("role") != "authenticated" or value.get("is_anonymous") is not False
            or value.get("deleted_at") is not None):
        raise EmailOtpDenied
    email = value.get("email")
    if not isinstance(email, str) or len(email) > 320 or not re.fullmatch(r"[^@\s]+@[^@\s]+", email):
        raise EmailOtpDenied
    if value.get("banned_until") is not None and _time(value["banned_until"]) > _now():
        raise EmailOtpDenied
    marker = value.get("email_confirmed_at")
    if marker is None and not confirmed:
        return email, None
    timestamp = _time(marker)
    if timestamp > _now():
        raise EmailOtpDenied
    return email, timestamp


def _time(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise EmailOtpDenied
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise EmailOtpDenied
    return result


class SupabaseEmailOtpVerifier:
    """Existing token binds the target; never accept a caller-selected email/user ID.

    No issuance, mail sending, persistence or route wiring.
    If called after future approval, /verify CONSUMES an OTP and creates a session;
    this PR calls it only through offline mocks. Use synchronous workers.
    """

    def __init__(self, *, project_url: str, audience: str, publishable_key: str):
        if not isinstance(publishable_key, str) or not re.fullmatch(r"sb_publishable_[A-Za-z0-9_-]{1,256}", publishable_key):
            raise ValueError("Expected a public publishable API key")
        self._verifier = SupabaseTokenVerifier(project_url, audience=audience)
        self._key, self._base = publishable_key, self._verifier.issuer

    def redeem(self, access_token: str, code: str) -> EmailOtpRedemption:
        try:
            if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code):
                raise EmailOtpDenied
            started, tick = _now(), monotonic()
            original = self._verifier.verify_claims(access_token)
            before = _json(_read_user(self._base + "/user", self._key, access_token))
            email, _ = _user(before, original.subject, self._verifier.audience, confirmed=False)
            # Binding email BEFORE consuming a code avoids redeeming another account's link/hash.
            response = _json(_post_verify(self._base + "/verify", self._key, email, code))
            token = response.get("access_token")
            verified = self._verifier.verify_claims(token)
            if verified.subject != original.subject or response.get("token_type") != "bearer":
                raise EmailOtpDenied
            if (verified.session_id == original.session_id or verified.issued_at < int(started.timestamp())
                    or verified.amr is None or not any(entry.method == "otp"
                    and entry.timestamp >= int(started.timestamp()) for entry in verified.amr)):
                raise EmailOtpDenied
            returned = response.get("user")
            if not isinstance(returned, dict):
                raise EmailOtpDenied
            returned_email, marker = _user(returned, original.subject, self._verifier.audience, confirmed=True)
            current = _json(_read_user(self._base + "/user", self._key, token))
            current_email, current_marker = _user(current, original.subject, self._verifier.audience, confirmed=True)
            if returned_email != email or current_email != email or current_marker != marker:
                raise EmailOtpDenied
            now = _now()
            if now.timestamp() >= min(original.expires_at, verified.expires_at) or monotonic() - tick > 3:
                raise EmailOtpUnavailable
            return EmailOtpRedemption(self._base, verified.subject, verified.session_id, email, marker, now)
        except (InvalidAccessToken, EmailOtpDenied):
            raise EmailOtpDenied("Email OTP redemption rejected") from None
        except HTTPError as error:
            try:
                status = error.code
                error.close()
            except Exception:
                raise EmailOtpUnavailable("Email OTP redemption unavailable") from None
            if status in {400, 401, 403, 404, 422}:
                raise EmailOtpDenied("Email OTP redemption rejected") from None
            raise EmailOtpUnavailable("Email OTP redemption unavailable") from None
        except Exception:
            raise EmailOtpUnavailable("Email OTP redemption unavailable") from None
