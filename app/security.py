"""High-entropy anonymous credentials and narrowly scoped group capabilities."""

import hashlib
import hmac
import re
import secrets
import time

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Credential, GroupInvitation


TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
OWNER_LIFETIME = 365 * 86400
INVITATION_LIFETIME = 600


def token_hash(token: str) -> str:
    # Random 256-bit credentials are not human passwords. SHA-256 is appropriate.
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def issue_credential(session, user_id: int) -> tuple[str, int]:
    token = secrets.token_urlsafe(32)
    expires = int(time.time()) + OWNER_LIFETIME
    session.add(Credential(user_id=user_id, token_hash=token_hash(token), expires_at=expires))
    session.flush()
    return token, expires


def unauthorized():
    return HTTPException(401, "Profile credential missing, invalid, or expired", headers={"WWW-Authenticate": "Bearer"})


def authenticate(session, authorization: str | None) -> int:
    prefix, _, token = (authorization or "").partition(" ")
    if prefix.lower() != "bearer" or not TOKEN_PATTERN.fullmatch(token):
        raise unauthorized()
    credential = session.scalar(select(Credential).where(Credential.token_hash == token_hash(token)))
    if credential is None or credential.expires_at <= int(time.time()):
        raise unauthorized()
    return credential.user_id


def require_owner(session, user_id: int, authorization: str | None) -> int:
    actual = authenticate(session, authorization)
    if actual != user_id:
        # Do not reveal whether another numeric ID exists.
        raise HTTPException(403, "This profile belongs to another credential")
    return actual


def issue_invitation(session, user_id: int) -> tuple[str, int]:
    from app.database import conflict_insert
    token = secrets.token_urlsafe(32)
    expires = int(time.time()) + INVITATION_LIFETIME
    session.execute(conflict_insert(GroupInvitation, session.get_bind().dialect.name)
                    .values(user_id=user_id, token_hash=token_hash(token), expires_at=expires)
                    .on_conflict_do_update(index_elements=["user_id"], set_={"token_hash": token_hash(token), "expires_at": expires}))
    return token, expires


def authorize_group(session, user_ids: list[int], invitations: dict[int, str], authorization: str | None) -> int:
    owner = authenticate(session, authorization)
    if owner not in user_ids:
        raise HTTPException(403, "Your profile must be in the group")
    for user_id in user_ids:
        if user_id == owner:
            continue
        token = invitations.get(user_id, "")
        grant = session.get(GroupInvitation, user_id)
        if (not TOKEN_PATTERN.fullmatch(token) or grant is None or grant.expires_at <= int(time.time())
                or not hmac.compare_digest(grant.token_hash, token_hash(token))):
            raise HTTPException(403, "A group invitation is missing, invalid, or expired")
    return owner
