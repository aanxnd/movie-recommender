"""Dormant owned username updates; no account linking or provider mutations."""
from fastapi import HTTPException
from pydantic import StrictStr, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import limits
from app.models import UserIdentity
from app.provisioning_principal import ProfileInput, ProvisioningPrincipal
from app.supabase_identity import resolve_verified_subject, UnresolvedIdentity, IdentityResolutionUnavailable


class UsernameInput(ProfileInput):
    revision: StrictStr

    @field_validator('revision')
    @classmethod
    def revision_policy(cls, value):
        if not value.isascii() or not value.isdecimal() or not 1 <= len(value) <= 19:
            raise ValueError('Invalid profile input')
        if not 0 < int(value) < 2**63 - 1 or str(int(value)) != value:
            raise ValueError('Invalid profile input')
        return value


def profile_settings(session_factory, principal, body=None):
    if type(principal) is not ProvisioningPrincipal or (body is not None and type(body) is not UsernameInput):
        raise HTTPException(401, 'Invalid authentication credentials')
    principal.require_fresh()
    try:
        # Persist abuse admission independently; conflicts must not refund quota.
        with session_factory() as session, session.begin():
            limits.consume(session, str(principal.subject), 'profile-settings', 30, 60)
        with session_factory() as session, session.begin():
            if session.info.get('lifecycle_enabled'):
                from app.deletion_guard import guard_subject
                guard_subject(session, principal.subject)
            identity = resolve_verified_subject(session, principal.subject)
            row = session.execute(select(UserIdentity.username, UserIdentity.profile_revision).where(
                UserIdentity.user_id == identity.user_id, UserIdentity.supabase_subject == principal.subject)).one()
            if row.username is None:
                raise UnresolvedIdentity
            if body is None:
                result = dict(status='ready', username=row.username, revision=str(row.profile_revision))
            else:
                changed = session.execute(update(UserIdentity).where(
                    UserIdentity.user_id == identity.user_id, UserIdentity.supabase_subject == principal.subject,
                    UserIdentity.profile_revision == int(body.revision)).values(
                        username=body.username, profile_revision=UserIdentity.profile_revision + 1).returning(
                            UserIdentity.username, UserIdentity.profile_revision)).one_or_none()
                if changed is None:
                    raise HTTPException(409, 'Profile changed; check again')
                result = dict(status='updated', username=changed.username, revision=str(changed.profile_revision))
            principal.require_fresh()  # Includes time spent waiting for the row/uniqueness locks.
        principal.require_fresh()
        return result
    except IntegrityError as error:
        constraint = getattr(getattr(error.orig, 'diag', None), 'constraint_name', None)
        if constraint == 'uq_identity_username_ci' or "UNIQUE constraint failed: index 'uq_identity_username_ci'" in str(error.orig):
            raise HTTPException(409, 'Username unavailable') from None
        raise HTTPException(503, 'Profile settings unavailable') from None
    except UnresolvedIdentity:
        raise HTTPException(401, 'Invalid authentication credentials') from None
    except (IdentityResolutionUnavailable, SQLAlchemyError):
        raise HTTPException(503, 'Profile settings unavailable') from None
