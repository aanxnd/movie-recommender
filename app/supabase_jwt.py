"""Dormant verification only: no identity linking, verified-email proof or access grant."""
import json
import re
from dataclasses import dataclass
from http.client import HTTPException
from threading import Lock
from time import monotonic
from typing import Literal
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import RFC_4122, UUID

import jwt


class InvalidAccessToken(ValueError):
    """Untrusted token; callers must use a fixed, secret-free error response."""


class SigningKeysUnavailable(RuntimeError):
    """No usable trusted key set; never fall back to unverified claims."""


@dataclass(frozen=True, slots=True, repr=False)
class AuthenticationMethodReference:
    """Signed historical method/time only, never a recent-MFA predicate."""

    method: str
    timestamp: int


@dataclass(frozen=True, slots=True, repr=False)
class VerifiedTokenClaims:
    """Token evidence only; obtain exclusively via verify_claims, not client objects.

    No live session, mailbox, local ownership, suspension or recent-MFA proof.
    Python types/immutability do not themselves establish evidence provenance.
    """

    subject: UUID
    session_id: UUID
    expires_at: int
    issued_at: int
    aal: Literal["aal1", "aal2"]
    amr: tuple[AuthenticationMethodReference, ...] | None


# Reviewed Supabase JWT Claims Reference methods; new methods need explicit review.
_AMR_METHODS = frozenset({"oauth", "password", "otp", "totp", "recovery", "invite",
                         "sso/saml", "magiclink", "email/signup", "email_change",
                         "token_refresh", "anonymous"})


def _timestamp(value):
    # Exact integer Unix seconds: no bool, string, fraction, negative or overflow.
    if type(value) is not int or not 0 <= value < 2**63:
        raise ValueError
    return value


def _session_uuid(value):
    if not isinstance(value, str):
        raise ValueError
    parsed = UUID(value)
    if str(parsed) != value or parsed.variant != RFC_4122:
        raise ValueError
    return parsed


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _download(url):
    # System TLS validation; no ambient proxies, credentials, redirects or token URLs.
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    with opener.open(Request(url, headers={"Accept": "application/json"}), timeout=3) as response:
        if response.status != 200:
            raise ValueError("JWKS response rejected")
        body = response.read(65537)
    if len(body) > 65536:
        raise ValueError("JWKS response too large")
    return body


def _parse(body):
    if not isinstance(body, bytes) or len(body) > 65536:
        raise ValueError("Invalid JWKS")
    document = json.loads(body)
    entries = document.get("keys") if isinstance(document, dict) else None
    if not isinstance(entries, list) or not 1 <= len(entries) <= 16:
        raise ValueError("Invalid JWKS")
    keys = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Invalid JWK")
        kid = entry.get("kid")
        if (not isinstance(kid, str) or not 1 <= len(kid) <= 128 or kid in keys
                or entry.get("alg") != "ES256" or entry.get("kty") != "EC"
                or entry.get("crv") != "P-256" or entry.get("use", "sig") != "sig"
                or entry.get("key_ops", ["verify"]) != ["verify"] or "d" in entry):
            raise ValueError("Unsupported JWK")
        keys[kid] = jwt.PyJWK.from_dict(entry, algorithm="ES256").key
    return keys


class SupabaseTokenVerifier:
    """Share one instance per process; call from a synchronous worker, not the event loop."""

    def __init__(self, project_url, *, audience="authenticated", fetch=_download, clock=monotonic):
        if not isinstance(project_url, str) or not re.fullmatch(r"https://[a-z0-9]{20}\.supabase\.co", project_url):
            raise ValueError("Expected a canonical hosted Supabase project origin")
        if not isinstance(audience, str) or not audience or len(audience) > 128:
            raise ValueError("Expected an explicit audience")
        self.issuer = project_url + "/auth/v1"
        self.jwks_url = self.issuer + "/.well-known/jwks.json"
        self.audience, self._fetch, self._clock = audience, fetch, clock
        self._keys, self._expires, self._retry_at = {}, 0, 0
        self._lock = Lock()

    def _key(self, kid):
        with self._lock:
            now = self._clock()
            if (now >= self._expires or kid not in self._keys) and now >= self._retry_at:
                # Coalesce concurrent refreshes and bound random-kid/outage traffic.
                self._retry_at = now + 30
                try:
                    keys = _parse(self._fetch(self.jwks_url))
                except (OSError, HTTPException, ValueError, TypeError, KeyError, RecursionError, jwt.PyJWTError):
                    raise SigningKeysUnavailable("Signing keys unavailable") from None
                self._keys, self._expires = keys, self._clock() + 300
            if self._clock() >= self._expires:
                raise SigningKeysUnavailable("Signing keys unavailable")
            return self._keys.get(kid)

    def verify(self, token) -> UUID:
        """Return only the canonical UUID subject; deliberately confer no authorization."""
        return UUID(self._verified_payload(token)["sub"])

    def verify_claims(self, token: str) -> VerifiedTokenClaims:
        """Verify the JWT before parsing typed session/AAL/AMR evidence; no access grant.

        AAL2/AMR do not prove recent MFA; expiry/session UUID do not prove a live
        session. Signed email cannot establish genuine mailbox verification.
        No user/factor/session lookup, account linking or authorization occurs.
        """
        claims = self._verified_payload(token)
        try:
            # Signature already verified: reject ambiguous JSON, including nested AMR.
            json.loads(jwt.utils.base64url_decode(token.split(".")[1]), object_pairs_hook=_unique_object)
            issued, expires = _timestamp(claims["iat"]), _timestamp(claims["exp"])
            if "nbf" in claims:
                _timestamp(claims["nbf"])
            session_id = _session_uuid(claims["session_id"])
            aal = claims["aal"]
            if not isinstance(aal, str) or aal not in ("aal1", "aal2"):
                raise ValueError
            amr = None
            if "amr" in claims:
                entries, methods = claims["amr"], set()
                if not isinstance(entries, list):
                    raise ValueError
                parsed = []
                for entry in entries:
                    if not isinstance(entry, dict) or set(entry) != {"method", "timestamp"}:
                        raise ValueError
                    method = entry["method"]
                    if not isinstance(method, str) or method not in _AMR_METHODS or method in methods:
                        raise ValueError
                    timestamp = _timestamp(entry["timestamp"])
                    if timestamp > issued:
                        raise ValueError
                    methods.add(method)
                    parsed.append(AuthenticationMethodReference(method, timestamp))
                amr = tuple(parsed)
            return VerifiedTokenClaims(UUID(claims["sub"]), session_id, expires, issued, aal, amr)
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
            raise InvalidAccessToken("Invalid access token") from None

    def _verified_payload(self, token):
        """Shared cryptographic checks; never accept an already-decoded payload."""
        try:
            if not isinstance(token, str) or not 1 <= len(token) <= 8192:
                raise ValueError
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if (header.get("alg") != "ES256" or header.get("typ", "JWT") != "JWT"
                    or not isinstance(kid, str) or not 1 <= len(kid) <= 128
                    or any(name in header for name in ("crit", "jku", "x5u", "jwk", "x5c"))):
                raise ValueError
            key = self._key(kid)
            if key is None:
                raise ValueError
            claims = jwt.decode(token, key, algorithms=["ES256"], issuer=self.issuer,
                                audience=self.audience, options={"strict_aud": True,
                                "require": ["iss", "aud", "exp", "iat", "sub", "role"]})
            if (claims["role"] != "authenticated" or claims["exp"] <= claims["iat"]
                    or any(type(claims[name]) is not int for name in ("exp", "iat", "nbf") if name in claims)):
                raise ValueError
            subject = UUID(claims["sub"])
            if str(subject) != claims["sub"] or subject.variant != RFC_4122:
                raise ValueError
            return claims
        except (jwt.PyJWTError, ValueError, TypeError, OverflowError, RecursionError):
            raise InvalidAccessToken("Invalid access token") from None
