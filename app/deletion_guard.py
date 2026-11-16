"""Transaction-level lifecycle fence, selected only by the explicit deletion candidate."""
from fastapi import HTTPException
from sqlalchemy import select, update

from app.deletion_store import intents
from app.models import User, UserIdentity


def guard_subject(session, subject):
    if not session.info.get('lifecycle_enabled'):
        return
    user_id = session.scalar(select(UserIdentity.user_id).where(UserIdentity.supabase_subject == subject))
    if user_id is not None:
        # Queue submission takes this same lock before installing the tombstone.
        session.execute(update(User).where(User.id == user_id).values(id=User.id))
    # A separate statement after the lock observes a queue commit we waited behind.
    if session.scalar(select(intents.c.request_id).where(intents.c.subject == subject)) is not None:
        raise HTTPException(401, 'Invalid authentication credentials', headers={'Cache-Control': 'no-store'})
