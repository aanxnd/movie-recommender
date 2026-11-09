"""Dormant lookup of a verifier-produced UUID; never an HTTP authentication boundary."""
from dataclasses import dataclass
from uuid import RFC_4122, UUID

from sqlalchemy import select
from sqlalchemy.exc import MultipleResultsFound, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import User, UserIdentity


class UnresolvedIdentity(ValueError):
    """Uniform rejection: do not reveal whether an account or link exists."""


class IdentityResolutionUnavailable(RuntimeError):
    """Database failure; callers own transaction rollback and a generic 503 response."""


@dataclass(frozen=True, slots=True, repr=False)
class AuthenticatedIdentity:
    """A resolved token subject, without email, MFA or resource-authorization proof."""

    subject: UUID
    user_id: int


def resolve_verified_subject(session: Session, subject: UUID) -> AuthenticatedIdentity:
    """Read an existing link; caller must obtain subject from SupabaseTokenVerifier.verify.

    UUID type checking cannot establish provenance. Never pass parsed client input.
    No cache, autoflush, writes, commit, rollback or session ownership here.
    """
    if type(subject) is not UUID or subject.variant != RFC_4122:
        raise UnresolvedIdentity("Identity could not be resolved")
    statement = (select(User.id).select_from(UserIdentity)
                 .join(User, User.id == UserIdentity.user_id)
                 .where(UserIdentity.supabase_subject == subject))
    try:
        # Avoid flushing pending links/users or trusting stale ORM identity-map objects.
        with session.no_autoflush:
            user_id = session.execute(statement).scalar_one_or_none()
    except MultipleResultsFound:
        raise UnresolvedIdentity("Identity could not be resolved") from None
    except SQLAlchemyError:
        raise IdentityResolutionUnavailable("Identity resolution unavailable") from None
    if type(user_id) is not int or not 0 < user_id < 2**63:
        raise UnresolvedIdentity("Identity could not be resolved")
    return AuthenticatedIdentity(subject=subject, user_id=user_id)
