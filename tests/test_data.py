from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

from app.data import load_movielens
from scripts.load_movielens import download_movielens


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    pd.DataFrame({
        "movieId": [1, 2],
        "title": ["Toy Story (1995)", "Jumanji (1995)"],
        "genres": ["Adventure|Animation", "Adventure|Fantasy"],
    }).to_csv(tmp_path / "movies.csv", index=False)
    pd.DataFrame({
        "userId": [1, 1, 2], "movieId": [1, 2, 1],
        "rating": [0.5, 5.0, 4.5], "timestamp": [1, 2, 3],
    }).to_csv(tmp_path / "ratings.csv", index=False)
    return tmp_path


def test_load_preserves_values_and_normalizes_columns(data_dir: Path) -> None:
    movies, ratings = load_movielens(data_dir)
    assert movies.columns.tolist() == ["movie_id", "title", "genres"]
    assert ratings.columns.tolist() == ["user_id", "movie_id", "rating"]
    assert movies.iloc[0].to_dict() == {
        "movie_id": 1, "title": "Toy Story (1995)", "genres": "Adventure|Animation",
    }
    assert ratings.to_dict("records") == [
        {"user_id": 1, "movie_id": 1, "rating": 0.5},
        {"user_id": 1, "movie_id": 2, "rating": 5.0},
        {"user_id": 2, "movie_id": 1, "rating": 4.5},
    ]


def test_missing_file_has_setup_instruction(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="scripts/load_movielens.py"):
        load_movielens(tmp_path)


@pytest.mark.parametrize("value", [0, 5.5, float("inf"), float("nan")])
def test_invalid_rating(data_dir: Path, value: float) -> None:
    path = data_dir / "ratings.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "rating"] = value
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError):
        load_movielens(data_dir)


@pytest.mark.parametrize("value", [0, -1, 1.5, float("inf")])
@pytest.mark.parametrize("filename,column", [
    ("ratings.csv", "userId"),
    ("movies.csv", "movieId"),
    ("ratings.csv", "movieId"),
])
def test_invalid_id(data_dir: Path, value: float, filename: str, column: str) -> None:
    path = data_dir / filename
    frame = pd.read_csv(path)
    frame[column] = frame[column].astype(float)
    frame.loc[0, column] = value
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="positive integers"):
        load_movielens(data_dir)


@pytest.mark.parametrize("filename,column", [
    ("ratings.csv", "userId"),
    ("movies.csv", "movieId"),
    ("ratings.csv", "movieId"),
])
@pytest.mark.parametrize("value", [2**63, 2**64 - 1, float(2**63)])
def test_oversized_id(data_dir: Path, filename: str, column: str, value: int | float) -> None:
    path = data_dir / filename
    frame = pd.read_csv(path)
    frame[column] = frame[column].astype(object)
    frame.loc[0, column] = value
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="IDs must fit in signed int64"):
        load_movielens(data_dir)


def test_signed_int64_maximum_id_is_preserved(data_dir: Path) -> None:
    maximum = 2**63 - 1
    for filename in ["movies.csv", "ratings.csv"]:
        path = data_dir / filename
        frame = pd.read_csv(path)
        frame.loc[frame["movieId"] == 1, "movieId"] = maximum
        if filename == "ratings.csv":
            frame.loc[frame["userId"] == 1, "userId"] = maximum
        frame.to_csv(path, index=False)
    movies, ratings = load_movielens(data_dir)
    assert movies["movie_id"].tolist() == [maximum, 2]
    assert ratings["movie_id"].tolist() == [maximum, 2, maximum]
    assert ratings["user_id"].tolist() == [maximum, maximum, 2]


@pytest.mark.parametrize("filename,columns,message", [
    ("movies.csv", ["movieId"], "duplicate movie IDs"),
    ("ratings.csv", ["userId", "movieId"], "duplicate user/movie pairs"),
])
def test_duplicates(data_dir: Path, filename: str, columns: list[str], message: str) -> None:
    path = data_dir / filename
    frame = pd.read_csv(path)
    for column in columns:
        frame.loc[1, column] = frame.loc[0, column]
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match=message):
        load_movielens(data_dir)


def test_unknown_movie_reference(data_dir: Path) -> None:
    path = data_dir / "ratings.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "movieId"] = 999
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="unknown movie"):
        load_movielens(data_dir)


def test_missing_column(data_dir: Path) -> None:
    path = data_dir / "movies.csv"
    pd.read_csv(path).drop(columns="genres").to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing columns.*genres"):
        load_movielens(data_dir)


def test_empty_dataset(data_dir: Path) -> None:
    (data_dir / "ratings.csv").write_text("userId,movieId,rating\n", encoding="utf-8")
    with pytest.raises(ValueError, match="nonempty"):
        load_movielens(data_dir)


def test_blank_title(data_dir: Path) -> None:
    path = data_dir / "movies.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "title"] = "   "
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="nonempty text"):
        load_movielens(data_dir)


def test_archive_import_preserves_readme_and_validates(data_dir: Path, tmp_path: Path) -> None:
    archive_path = tmp_path / "sample.zip"
    with ZipFile(archive_path, "w") as archive:
        for name in ["movies.csv", "ratings.csv"]:
            archive.write(data_dir / name, f"ml-latest-small/{name}")
        archive.writestr("ml-latest-small/README.txt", "Dataset usage terms")
        archive.writestr("ml-latest-small/tags.csv", "unused")
    destination = tmp_path / "imported"
    download_movielens(destination, archive_path)
    movies, ratings = load_movielens(destination)
    assert len(movies) == 2
    assert len(ratings) == 3
    assert (destination / "README.txt").read_text() == "Dataset usage terms"
    assert not (destination / "tags.csv").exists()
