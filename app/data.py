"""Load and validate historical MovieLens data, separate from app ratings."""

from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path}. Run python scripts/load_movielens.py first."
        )
    frame = pd.read_csv(path)
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
    frame = frame[columns].copy()
    if frame.empty or frame.isna().any().any():
        raise ValueError(f"{path.name}: data must be nonempty with no missing values")
    return frame


def _validate_ids(frame: pd.DataFrame, columns: list[str]) -> None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="raise")
        if not (np.isfinite(values) & (values > 0) & (values % 1 == 0)).all():
            raise ValueError(f"{column}: IDs must be positive integers")
        if values.map(lambda value: int(value) > np.iinfo(np.int64).max).any():
            raise ValueError(f"{column}: IDs must fit in signed int64")
        frame[column] = values.astype("int64")


def load_movielens(data_dir: Path = DEFAULT_DATA_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return movies and ratings with normalized, explicit column names.

    MovieLens IDs remain unchanged. Historical user IDs belong to MovieLens,
    not to the application's SQLite users table.
    """
    movies = _read_csv(Path(data_dir) / "movies.csv", ["movieId", "title", "genres"])
    ratings = _read_csv(Path(data_dir) / "ratings.csv", ["userId", "movieId", "rating"])
    movies.rename(columns={"movieId": "movie_id"}, inplace=True)
    ratings.rename(columns={"userId": "user_id", "movieId": "movie_id"}, inplace=True)
    _validate_ids(movies, ["movie_id"])
    _validate_ids(ratings, ["user_id", "movie_id"])
    if movies["movie_id"].duplicated().any():
        raise ValueError("movies.csv: duplicate movie IDs")
    for column in ["title", "genres"]:
        if not movies[column].map(lambda value: isinstance(value, str) and bool(value.strip())).all():
            raise ValueError(f"movies.csv: {column} must contain nonempty text")
    ratings["rating"] = pd.to_numeric(ratings["rating"], errors="raise")
    if not ratings["rating"].between(0.5, 5.0).all():
        raise ValueError("ratings.csv: ratings must be between 0.5 and 5.0")
    if ratings.duplicated(["user_id", "movie_id"]).any():
        raise ValueError("ratings.csv: duplicate user/movie pairs")
    if not ratings["movie_id"].isin(movies["movie_id"]).all():
        raise ValueError("ratings.csv: rating references an unknown movie")
    return movies, ratings
