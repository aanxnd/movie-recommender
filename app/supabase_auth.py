"""Dormant FastAPI composition; token/link authentication is not authorization."""
from collections.abc import Callable
from dataclasses import dataclass
import re

from fastapi import HTTPException, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.supabase_identity import IdentityResolutionUnavailable, UnresolvedIdentity, resolve_verified_subject
from app.supabase_jwt import InvalidAccessToken, SigningKeysUnavailable, SupabaseTokenVerifier


@dataclass(frozen=True, slots=True, repr=False)
class SupabaseAuthContext:
    """Resolved caller ID only; no verified-email, MFA, session-state or access proof."""

    user_id: int


def _invalid_credentials():
    return HTTPException(401, "Invalid authentication credentials",
                         headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"})


def make_supabase_auth_dependency(*, project_url: str, audience: str,
                                  session_factory: Callable[[], Session]) -> Callable[..., SupabaseAuthContext]:
    """Explicit server-only construction, once per process; no network or DB work here.

    session_factory must create a fresh Session, not return a shared/request session.
    Use the returned function through Depends; never call it on an async event loop.
    """
    verifier = SupabaseTokenVerifier(project_url, audience=audience)

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
            subject = verifier.verify(match.group(1).decode("ascii"))
            # All blocking work and session lifetime stay inside this sync dependency.
            with session_factory() as session, session.begin():
                identity = resolve_verified_subject(session, subject)
                context = SupabaseAuthContext(user_id=identity.user_id)
            return context
        except (InvalidAccessToken, UnresolvedIdentity):
            raise _invalid_credentials() from None
        except (SigningKeysUnavailable, IdentityResolutionUnavailable, SQLAlchemyError):
            raise HTTPException(503, "Authentication temporarily unavailable",
                                headers={"Cache-Control": "no-store", "Retry-After": "30"}) from None

    return authenticate
