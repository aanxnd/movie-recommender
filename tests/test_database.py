from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import (
    DEFAULT_DATABASE_PATH, create_database_engine, create_schema, create_user,
    get_rating, get_user, get_user_profile, get_user_ratings, register_movies, save_rating,
)
from app.models import Movie, UserRating
from app.recommender import recommend


@pytest.fixture
def engine(tmp_path: Path):
    engine = create_database_engine(tmp_path / "nested" / "test.db")
    create_schema(engine)
    with Session(engine) as session, session.begin():
        register_movies(session, [10, 20, 30])
    yield engine
    engine.dispose()


def test_schema_and_id_only_catalog(engine):
    create_schema(engine)
    assert set(inspect(engine).get_table_names()) == {"users", "movies", "user_ratings"}
    with Session(engine) as session, session.begin():
        register_movies(session, [10, 20])
        assert list(session.scalars(select(Movie.movie_id).order_by(Movie.movie_id))) == [10, 20, 30]


def test_default_path_is_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert DEFAULT_DATABASE_PATH == Path(__file__).resolve().parents[1] / "data" / "application.db"


def test_unique_users_and_persistence_across_engines(engine):
    with Session(engine) as session, session.begin():
        first = create_user(session).id
        second = create_user(session).id
        assert first != second
        save_rating(session, first, 10, 4.5)
    reopened = create_database_engine(Path(engine.url.database))
    try:
        with Session(reopened) as session, session.begin():
            assert get_user(session, first).id == first
            assert get_user(session, second).id == second
            assert get_rating(session, first, 10).rating == 4.5
            assert create_user(session).id not in {first, second}
            assert get_user(session, 999) is None
    finally:
        reopened.dispose()


def test_rating_update_multiple_ratings_and_user_isolation(engine):
    with Session(engine) as session, session.begin():
        first = create_user(session).id
        second = create_user(session).id
        assert get_user_profile(session, first) == {}
        assert get_rating(session, first, 10) is None
        original = save_rating(session, first, 10, 0.5)
        save_rating(session, first, 20, 5.0)
        save_rating(session, second, 10, 2.0)
        updated = save_rating(session, first, 10, 4.0)
        assert original is updated
        assert updated.rating == 4.0
        assert len(get_user_ratings(session, first)) == 2
        assert get_user_profile(session, first) == {10: 4.0, 20: 5.0}
        assert get_user_profile(session, second) == {10: 2.0}
        # Application ID 1 does not exclude historical MovieLens user 1.
        assert recommend(get_user_profile(session, first), {1: {10: 4, 20: 5, 30: 3}}) == [(30, 3.5)]


@pytest.mark.parametrize("rating", [0, 0.49, 5.01, float("nan"), float("inf"), -float("inf"), True, "4", 10**1000])
def test_invalid_rating_does_not_change_existing_value(engine, rating):
    with Session(engine) as session, session.begin():
        user_id = create_user(session).id
        save_rating(session, user_id, 10, 3.0)
        with pytest.raises(ValueError, match="rating must"):
            save_rating(session, user_id, 10, rating)
        assert get_user_profile(session, user_id) == {10: 3.0}


def test_unknown_users_and_movies(engine):
    with Session(engine) as session, session.begin():
        user_id = create_user(session).id
        for operation in (
            lambda: save_rating(session, 999, 10, 4),
            lambda: get_rating(session, 999, 10),
            lambda: get_user_ratings(session, 999),
            lambda: get_user_profile(session, 999),
        ):
            with pytest.raises(ValueError, match="Unknown application user"):
                operation()
        with pytest.raises(ValueError, match="Unknown MovieLens movie"):
            save_rating(session, user_id, 999, 4)
        assert get_user_profile(session, user_id) == {}


@pytest.mark.parametrize("value", [0, -1, True, 1.5, 2**63])
def test_invalid_ids(engine, value):
    with Session(engine) as session, session.begin():
        with pytest.raises(ValueError, match="positive signed int64"):
            get_user(session, value)
        with pytest.raises(ValueError, match="positive signed int64"):
            register_movies(session, [value])


@pytest.mark.parametrize("rows", [
    [(1, 10, 0.0)], [(1, 10, 5.5)], [(999, 10, 4.0)], [(1, 999, 4.0)],
    [(1, 10, 4.0), (1, 10, 3.0)],
])
def test_database_constraints_reject_direct_invalid_writes(engine, rows):
    with Session(engine) as session, session.begin():
        assert create_user(session).id == 1
    with pytest.raises(IntegrityError):
        with Session(engine) as session, session.begin():
            session.add_all(UserRating(user_id=u, movie_id=m, rating=r) for u, m, r in rows)
            session.flush()
    with Session(engine) as session:
        assert get_user_profile(session, 1) == {}


def test_failed_transaction_rolls_back_user_and_rating(engine):
    with pytest.raises(ValueError):
        with Session(engine) as session, session.begin():
            user_id = create_user(session).id
            save_rating(session, user_id, 10, 4)
            save_rating(session, user_id, 999, 4)
    with Session(engine) as session:
        assert get_user(session, user_id) is None
