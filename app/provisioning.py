"""Dormant transactional new-profile service. Never claims or repairs historical users."""
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import database, limits
from app.models import User, UserIdentity
from app.provisioning_principal import ProfileInput, ProvisioningPrincipal, valid_username


@dataclass(frozen=True, slots=True, repr=False)
class ProvisionedProfile:
    user_id: int  # Internal only; the HTTP/UI contract exposes just username.
    username: str


def unavailable():
    return HTTPException(503, "Profile setup unavailable; check again before retrying",
                         headers={"Cache-Control": "no-store", "Retry-After": "30"})


def _lookup(session, subject):
    row = session.execute(select(UserIdentity.user_id, UserIdentity.username, User.id)
                          .outerjoin(User, User.id == UserIdentity.user_id)
                          .where(UserIdentity.supabase_subject == subject)).one_or_none()
    if row is None:
        return None
    if (type(row[0]) is not int or not 0 < row[0] < 2**63 or row[0] != row[2]
            or not valid_username(row[1])):
        raise unavailable()
    return ProvisionedProfile(row[0], row[1])


def _trusted(principal):
    # Server code must obtain this only from make_provisioning_dependency; this
    # type check does not turn client UUIDs or booleans into verified evidence.
    if (type(principal) is not ProvisioningPrincipal or type(principal.subject) is not UUID
            or not principal.subject.int):
        raise unavailable()
    principal.require_fresh()


def inspect_profile(session_factory, principal):
    _trusted(principal)
    try:
        with session_factory() as session, session.begin():
            result = _lookup(session, principal.subject)
        principal.require_fresh()
        return result
    except SQLAlchemyError:
        raise unavailable() from None


def provision_profile(session_factory, principal, input: ProfileInput, *, maximum=limits.MAX_PROFILES):
    _trusted(principal)
    if type(input) is not ProfileInput:
        raise unavailable()
    try:
        with session_factory() as session, session.begin():
            result = _lookup(session, principal.subject)
            if result is None:
                # Shared with legacy creation. Recheck after acquiring the lock:
                # another process may have committed this subject at capacity.
                database.lock_user_capacity(session)
                result = _lookup(session, principal.subject)
                if result is None:
                    database.enforce_user_capacity(session, maximum)
                    user = database.create_user(session)
                    session.add(UserIdentity(user_id=user.id, supabase_subject=principal.subject,
                                             username=input.username))
                    session.flush()  # Unique subject, user and lower(username) are DB-enforced.
                    result = ProvisionedProfile(user.id, input.username)
            principal.require_fresh()
        principal.require_fresh()
        return result
    except SQLAlchemyError as error:
        # The failed Session/transaction is closed before any recovery read. An
        # acknowledgement can be lost after COMMIT; never blindly repeat INSERT.
        try:
            with session_factory() as clean, clean.begin():
                result = _lookup(clean, principal.subject)
                conflict = isinstance(error, IntegrityError)
                if result is None and conflict:
                    from sqlalchemy import func
                    conflict = clean.scalar(select(UserIdentity.user_id).where(
                        func.lower(UserIdentity.username) == input.username.lower())) is not None
            principal.require_fresh()
            if result is not None:
                return result
            if conflict:
                raise HTTPException(409, "Username unavailable", headers={"Cache-Control": "no-store"}) from None
        except SQLAlchemyError:
            pass
        raise unavailable() from None
