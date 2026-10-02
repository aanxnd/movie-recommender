"""Explicit SQLite setup and application-user operations.

Writes flush within the caller's transaction. Use Session.begin() to commit
on success and roll back on failure; reads do not commit.
"""

from collections.abc import Iterable
from math import isfinite
from pathlib import Path

from sqlalchemy import Engine, URL, create_engine, event, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.models import Base, Movie, User, UserRating


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "application.db"


def create_database_engine(path: Path = DEFAULT_DATABASE_PATH) -> Engine:
    """Create an engine; the default path is anchored to the repository."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(URL.create("sqlite", database=str(path)))

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, connection_record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def register_movies(session: Session, movie_ids: Iterable[int]) -> None:
    """Register validated MovieLens catalog IDs without copying CSV metadata."""
    ids = sorted(set(movie_ids))
    for movie_id in ids:
        _validate_id(movie_id, "movie_id")
    if ids:
        session.execute(
            insert(Movie).on_conflict_do_nothing(index_elements=["movie_id"]),
            [{"movie_id": movie_id} for movie_id in ids],
        )


def _validate_id(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value < 2**63:
        raise ValueError(f"{name} must be a positive signed int64 integer")


def create_user(session: Session) -> User:
    user = User()
    session.add(user)
    session.flush()
    return user


def get_user(session: Session, user_id: int) -> User | None:
    _validate_id(user_id, "user_id")
    return session.get(User, user_id)


def _require_user(session: Session, user_id: int) -> None:
    if get_user(session, user_id) is None:
        raise ValueError(f"Unknown application user: {user_id}")


def save_rating(session: Session, user_id: int, movie_id: int, rating: float) -> UserRating:
    _require_user(session, user_id)
    _validate_id(movie_id, "movie_id")
    if isinstance(rating, bool) or not isinstance(rating, (int, float)):
        raise ValueError("rating must be a finite number between 0.5 and 5.0")
    if not 0.5 <= rating <= 5.0 or not isfinite(rating):
        raise ValueError("rating must be a finite number between 0.5 and 5.0")
    if session.get(Movie, movie_id) is None:
        raise ValueError(f"Unknown MovieLens movie: {movie_id}")
    session.execute(
        insert(UserRating).values(user_id=user_id, movie_id=movie_id, rating=float(rating))
        .on_conflict_do_update(
            index_elements=["user_id", "movie_id"], set_={"rating": float(rating)}
        )
    )
    return session.get(UserRating, (user_id, movie_id), populate_existing=True)


def get_rating(session: Session, user_id: int, movie_id: int) -> UserRating | None:
    _require_user(session, user_id)
    _validate_id(movie_id, "movie_id")
    return session.get(UserRating, (user_id, movie_id))


def get_user_ratings(session: Session, user_id: int) -> list[UserRating]:
    _require_user(session, user_id)
    return list(session.scalars(
        select(UserRating).where(UserRating.user_id == user_id).order_by(UserRating.movie_id)
    ))


def get_user_profile(session: Session, user_id: int) -> dict[int, float]:
    """Return the sparse profile consumed directly by Stage 2 recommend()."""
    return {row.movie_id: row.rating for row in get_user_ratings(session, user_id)}
