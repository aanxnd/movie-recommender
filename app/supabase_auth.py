"""Dormant FastAPI composition; token/link authentication is not authorization."""
from collections.abc import Callable
from dataclasses import dataclass
import re
from time import time
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.supabase_identity import IdentityResolutionUnavailable, UnresolvedIdentity, resolve_verified_subject
from app.supabase_policy import AccessDenied, AccessUnavailable, SupabaseAccessPolicy


@dataclass(frozen=True, slots=True, repr=False)
class SupabaseAuthContext:
    """Server-built principal; never serialize/log it or infer resource permissions."""

    user_id: int
    subject: UUID
    email: str
    aal: Literal["aal1", "aal2"]


def _invalid_credentials():
    return HTTPException(401, "Invalid authentication credentials",
                         headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"})


def make_supabase_auth_dependency(*, project_url: str, audience: str, publishable_key: str,
                                  session_factory: Callable[[], Session]) -> Callable[..., SupabaseAuthContext]:
    """Explicit server-only construction, once per process; no network or DB work here.

    session_factory must create a fresh Session, not return a shared/request session.
    Use the returned function through Depends; never call it on an async event loop.
    """
    policy = SupabaseAccessPolicy(project_url=project_url, audience=audience, publishable_key=publishable_key)

    def authenticate(request: Request, response: Response) -> SupabaseAuthContext:
        # Raw headers preserve duplicates, including differently cased field names.
        values = [value for name, value in request.scope["headers"] if name.lower() == b"authorization"]
        response.headers["Cache-Control"] = "no-store"
        if len(values) != 1 or len(values[0]) > 8199:
            raise _invalid_credentials()
        match = re.fullmatch(rb"(?i:Bearer) ([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)", values[0])
        if match is None:
            raise _invalid_credentials()
        try:
            claims, email = policy.check_with_email(match.group(1).decode("ascii"))
            # All blocking work and session lifetime stay inside this sync dependency.
            with session_factory() as session, session.begin():
                identity = resolve_verified_subject(session, claims.subject)
                context = SupabaseAuthContext(user_id=identity.user_id, subject=claims.subject,
                                              email=email.email, aal=claims.aal)
            if claims.expires_at <= time():
                raise AccessDenied
            return context
        except (AccessDenied, UnresolvedIdentity):
            raise _invalid_credentials() from None
        except (AccessUnavailable, IdentityResolutionUnavailable, SQLAlchemyError):
            raise HTTPException(503, "Authentication temporarily unavailable",
                                headers={"Cache-Control": "no-store", "Retry-After": "30"}) from None

    return authenticate
