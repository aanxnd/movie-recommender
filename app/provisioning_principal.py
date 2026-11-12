"""Dormant new-account boundary: no existing numeric identity is required or granted."""
from dataclasses import dataclass
from time import time
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, StrictStr, field_validator

from app.supabase_auth import _bearer_token, _invalid_credentials
from app.supabase_policy import AccessDenied, AccessUnavailable, SupabaseAccessPolicy


RESERVED_USERNAMES = frozenset({"admin", "administrator", "api", "auth", "help", "login", "logout",
                              "movelle", "root", "security", "settings", "signup", "support", "system"})


def valid_username(value):
    # Preserve display case; ASCII lower() is the database uniqueness policy.
    import re
    return (type(value) is str and re.fullmatch(r"[A-Za-z0-9_]{3,30}", value) is not None
            and value.lower() not in RESERVED_USERNAMES)


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    username: StrictStr

    @field_validator("username")
    @classmethod
    def username_policy(cls, value):
        if not valid_username(value):
            raise ValueError("Invalid profile input")
        return value


@dataclass(frozen=True, slots=True, repr=False)
class ProvisioningPrincipal:
    """Trusted server-only evidence, never a request model or resource access grant.

    Only the dependency below constructs this from verified claims. Token expiry,
    AAL and session ID do not prove immediate revocation or recent MFA.
    """
    subject: UUID
    session_id: UUID
    expires_at: int
    aal: Literal["aal1", "aal2"]

    def require_fresh(self):
        if self.expires_at <= time():
            raise _invalid_credentials()


def make_provisioning_dependency(*, project_url: str, audience: str, publishable_key: str):
    """Explicit dormant composition; no DB resolution, network on construction or legacy fallback."""
    policy = SupabaseAccessPolicy(project_url=project_url, audience=audience, publishable_key=publishable_key)

    def authenticate(request: Request, response: Response) -> ProvisioningPrincipal:
        token = _bearer_token(request, response)
        try:
            claims = policy.check_for_provisioning(token)
            principal = ProvisioningPrincipal(claims.subject, claims.session_id, claims.expires_at, claims.aal)
            principal.require_fresh()
            return principal
        except AccessDenied:
            raise _invalid_credentials() from None
        except AccessUnavailable:
            raise HTTPException(503, "Authentication temporarily unavailable",
                                headers={"Cache-Control": "no-store", "Retry-After": "30"}) from None

    return authenticate
