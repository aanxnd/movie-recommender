"""Dormant owner-scoped operations; principals must come from Depends(authenticate)."""
from contextlib import contextmanager
from uuid import UUID, RFC_4122

from fastapi import HTTPException
from sqlalchemy import and_, delete, literal, select
from sqlalchemy.exc import SQLAlchemyError

from app import database, limits
from app.models import Movie, User, UserIdentity, UserRating
from app.supabase_auth import SupabaseAuthContext


def _denied():
    return HTTPException(404, "Resource unavailable", headers={"Cache-Control": "no-store"})


@contextmanager
def _storage(session):
    try:
        with session.no_autoflush:
            yield
    except SQLAlchemyError:
        raise HTTPException(503, "Resource service unavailable",
                            headers={"Cache-Control": "no-store", "Retry-After": "30"}) from None


def _id(value):
    if type(value) is not int or not 0 < value < 2**63:
        raise _denied()
    return value


def _binding(principal):
    # Type checks do not establish authentication provenance. Never deserialize a
    # request into this class; only the central dependency may supply the caller.
    if (type(principal) is not SupabaseAuthContext or type(principal.subject) is not UUID
            or principal.subject.variant != RFC_4122):
        raise _denied()
    _id(principal.user_id)
    return (select(User.id).join(UserIdentity, UserIdentity.user_id == User.id)
            .where(User.id == principal.user_id, UserIdentity.supabase_subject == principal.subject)
            .correlate(None).exists())


def _scope(principal, owner, target):
    binding = _binding(principal)
    return and_(owner == principal.user_id, owner == _id(target), binding)


def require_profile_owner(session, principal: SupabaseAuthContext, user_id: int) -> int:
    """Private profile/settings/invitation guard; not a reusable write capability."""
    with _storage(session):
        found = session.scalar(select(User.id).where(_scope(principal, User.id, user_id)))
        if found is None:
            raise _denied()
        return found


def read_ratings(session, principal: SupabaseAuthContext, user_id: int, *, after=0, limit=100) -> dict[int, float]:
    """Owner-only rating/saved-movie page; metadata remains in the public catalog."""
    if type(after) is not int or not 0 <= after < 2**63 or type(limit) is not int or not 1 <= limit <= 100:
        raise _denied()
    with _storage(session):
        rows = session.execute(select(User.id, UserRating.movie_id, UserRating.rating)
            .outerjoin(UserRating, and_(UserRating.user_id == User.id, UserRating.movie_id > after))
            .where(_scope(principal, User.id, user_id)).order_by(UserRating.movie_id).limit(limit)).all()
        if not rows:
            raise _denied()
        return {movie: rating for _, movie, rating in rows if movie is not None}


def put_rating(session, principal: SupabaseAuthContext, user_id: int, movie_id: int, rating: float) -> float:
    """Whitelist only rating; derive the inserted owner from the bound User row."""
    movie_id = _id(movie_id)
    if type(rating) not in (int, float) or not 0.5 <= rating <= 5:
        raise _denied()
    value = float(rating)
    with _storage(session):
        require_profile_owner(session, principal, user_id)
        # Reuse existing quota serialization. The mutation still rechecks binding
        # atomically; the preceding guard must never authorize an unscoped write.
        database.enforce_rating_quota(session, principal.user_id, movie_id, limits.MAX_PROFILE_RATINGS)
        source = select(User.id, literal(movie_id), literal(value)).where(
            _scope(principal, User.id, user_id),
            select(Movie.movie_id).where(Movie.movie_id == movie_id).exists())
        statement = database.conflict_insert(UserRating, session.get_bind().dialect.name).from_select(
            ["user_id", "movie_id", "rating"], source)
        found = session.scalar(statement.on_conflict_do_update(index_elements=["user_id", "movie_id"],
            set_={"rating": value}, where=_scope(principal, UserRating.user_id, user_id)).returning(UserRating.movie_id))
        if found is None:
            raise _denied()
    return value


def delete_rating(session, principal: SupabaseAuthContext, user_id: int, movie_id: int) -> None:
    with _storage(session):
        found = session.scalar(delete(UserRating).where(_scope(principal, UserRating.user_id, user_id),
            UserRating.movie_id == _id(movie_id)).returning(UserRating.movie_id))
        if found is None:
            raise _denied()
