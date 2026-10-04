"""SQLite/PostgreSQL setup and application-user operations.

Writes flush within the caller's transaction. Use Session.begin() to commit
on success and roll back on failure; reads do not commit.
"""

from collections.abc import Iterable
from math import isfinite
import os
from pathlib import Path

from sqlalchemy import Engine, URL, create_engine, event, select
from sqlalchemy.engine import make_url
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session

from app.models import Base, Movie, User, UserRating


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "application.db"


def create_database_engine(path: Path | None = None, *, database_url: str | None = None) -> Engine:
    """Explicit path > explicit URL > DATABASE_URL > repository SQLite path."""
    if path is not None:
        url = URL.create("sqlite", database=str(Path(path).resolve()))
    else:
        configured = database_url if database_url is not None else os.environ.get("DATABASE_URL")
        try:
            url = make_url(configured) if configured else URL.create("sqlite", database=str(DEFAULT_DATABASE_PATH))
        except Exception:
            raise ValueError("Invalid database configuration") from None
    backend = url.get_backend_name()
    if backend == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
        return create_engine(
            url, pool_pre_ping=True, pool_size=2, max_overflow=0, pool_timeout=3,
            connect_args={"connect_timeout": 5, "prepare_threshold": None},
            hide_parameters=True,
        )
    if backend != "sqlite" or url.drivername not in {"sqlite", "sqlite+pysqlite"}:
        raise ValueError("Only SQLite and PostgreSQL databases are supported")
    if url.database and url.database != ":memory:":
        file_path = Path(url.database).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        url = url.set(database=str(file_path))
    engine = create_engine(url, connect_args={"timeout": 3}, hide_parameters=True)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, connection_record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def conflict_insert(model, dialect: str):
    """Use each database's native atomic ON CONFLICT implementation."""
    if dialect == "sqlite":
        return sqlite_insert(model)
    if dialect == "postgresql":
        return postgresql_insert(model)
    raise ValueError("Unsupported database dialect")


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def register_movies(session: Session, movie_ids: Iterable[int]) -> None:
    """Register validated MovieLens catalog IDs without copying CSV metadata."""
    ids = sorted(set(movie_ids))
    for movie_id in ids:
        _validate_id(movie_id, "movie_id")
    dialect = session.get_bind().dialect.name
    for start in range(0, len(ids), 1000):
        batch = [{"movie_id": movie_id} for movie_id in ids[start:start + 1000]]
        statement = conflict_insert(Movie, dialect)
        if dialect == "postgresql":
            statement = statement.values(batch).on_conflict_do_nothing(index_elements=["movie_id"])
            session.execute(statement)
            continue
        session.execute(
            statement.on_conflict_do_nothing(index_elements=["movie_id"]), batch,
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
        conflict_insert(UserRating, session.get_bind().dialect.name).values(user_id=user_id, movie_id=movie_id, rating=float(rating))
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
    """Return application ratings as a sparse recommendation profile."""
    return {row.movie_id: row.rating for row in get_user_ratings(session, user_id)}
