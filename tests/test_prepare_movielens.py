import numpy as np
import pytest

from app.historical import ARRAY_DTYPES, checksum, load_prepared
from scripts.prepare_movielens import positive_id, prepare_movielens


@pytest.fixture
def source(tmp_path):
    (tmp_path / "movies.csv").write_text('movieId,title,genres\n20,B (2000),Drama\n10,A (1999),Action|Sci-Fi\n30,Unknown,Comedy\n', encoding="utf-8")
    (tmp_path / "ratings.csv").write_text('userId,movieId,rating,timestamp\n2,10,0.5,1\n2,20,5,2\n9,10,4.5,3\n', encoding="utf-8")
    (tmp_path / "README.txt").write_text("Fixture terms", encoding="utf-8")
    return tmp_path


def test_prepared_contents_and_semantic_determinism(source):
    first = load_prepared(prepare_movielens(source, source / "first", chunk_size=1), verify=True)
    second = load_prepared(prepare_movielens(source, source / "second", chunk_size=10), verify=True)
    for name, dtype in ARRAY_DTYPES.items():
        assert first.arrays[name].dtype == np.dtype(dtype)
        assert np.array_equal(first.arrays[name], second.arrays[name])
        assert not first.arrays[name].flags.writeable
    assert {key: value for key, value in first.manifest.items() if key != "artifact_checksums"} == {
        key: value for key, value in second.manifest.items() if key != "artifact_checksums"}
    assert first.catalog == second.catalog
    assert first.arrays["user_ids"].tolist() == [2, 9]
    assert first.arrays["user_offsets"].tolist() == [0, 2, 3]
    assert first.arrays["movie_ids"].tolist() == [10, 20, 30]
    assert first.arrays["profile_movie_indices"].tolist() == [0, 1, 0]
    assert first.arrays["profile_ratings"].tolist() == [.5, 5, 4.5]
    assert first.arrays["user_means"].tolist() == [2.75, 4.5]
    assert first.arrays["movie_counts"].tolist() == [2, 1, 0]
    assert first.arrays["movie_totals"].tolist() == [5, 5, 0]
    assert first.arrays["popularity_order"].tolist() == [1, 0]
    assert first.postings(0).tolist() == [0, 1]
    assert first.manifest["global_mean"] == 10 / 3
    assert first.manifest["source_checksums"]["ratings.csv"] == checksum(source / "ratings.csv")
    assert [row["movie_id"] for row in first.catalog["movies"]] == [20, 10, 30]
    assert first.catalog["decades"] == [1990, 2000]
    assert first.catalog["genre_movies"]["drama"] == [20]
    assert first.catalog["decade_movies"]["1990"] == [10]
    assert first.movie_index(30) == 2 and first.movie_index(999) is None
    with pytest.raises(KeyError):
        first.user_index(999)


@pytest.mark.parametrize("contents,match", [
    ("userId,movieId,rating\n", "nonempty"),
    ("userId,movieId\n2,10\n", "missing columns"),
    ("userId,movieId,rating\n2,10,4\n2,10,5\n", "duplicate"),
    ("userId,movieId,rating\n2,20,4\n2,10,5\n", "ordered"),
    ("userId,movieId,rating\n9,10,4\n2,20,5\n", "ordered"),
    ("userId,movieId,rating\n2,999,4\n", "unknown movie"),
    ("userId,movieId,rating\n2,10,NaN\n", "finite"),
    ("userId,movieId,rating\n2,10,Infinity\n", "finite"),
    ("userId,movieId,rating\n2,10,5.1\n", "finite"),
    ("userId,movieId,rating\n2,10,\n", "invalid rating"),
    ("userId,movieId,rating\n0,10,4\n", "positive integers"),
    ("userId,movieId,rating\n9223372036854775808,10,4\n", "signed int64"),
])
def test_invalid_ratings_never_publish(source, contents, match):
    (source / "ratings.csv").write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        prepare_movielens(source, source / "prepared", chunk_size=1)
    assert not (source / "prepared").exists()
    assert not list(source.glob(".staging-*"))


@pytest.mark.parametrize("contents,match", [
    ("movieId,title,genres\n10,A,Drama\n10,B,Action\n", "duplicate"),
    ("movieId,title,genres\n10, ,Drama\n", "nonempty text"),
    ("movieId,title,genres\n10,A,\n", "nonempty text"),
    ("movieId,title\n10,A\n", "missing columns"),
])
def test_invalid_catalog(source, contents, match):
    (source / "movies.csv").write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        prepare_movielens(source, source / "prepared")


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "NaN", "Infinity", "", "garbage", "9223372036854775808"])
def test_invalid_ids(value):
    with pytest.raises(ValueError):
        positive_id(value)


def test_signed_int64_id_boundary(source):
    maximum = str(2**63 - 1)
    (source / "movies.csv").write_text(f"movieId,title,genres\n{maximum},A,Drama\n", encoding="utf-8")
    (source / "ratings.csv").write_text(f"userId,movieId,rating\n{maximum},{maximum},3.25\n", encoding="utf-8")
    data = load_prepared(prepare_movielens(source, source / "prepared"), verify=True)
    assert int(data.arrays["movie_ids"][0]) == int(maximum)
    assert int(data.arrays["user_ids"][0]) == int(maximum)
    assert float(data.arrays["profile_ratings"][0]) == 3.25


def test_refuses_overwrite_and_bad_chunk_size(source):
    output = prepare_movielens(source, source / "prepared")
    with pytest.raises(FileExistsError):
        prepare_movielens(source, output)
    with pytest.raises(ValueError, match="chunk_size"):
        prepare_movielens(source, source / "other", chunk_size=0)


def test_source_mutation_does_not_publish(source, monkeypatch):
    import scripts.prepare_movielens as preparation
    original = preparation.rating_chunks
    calls = 0

    def changing(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            (source / "ratings.csv").write_text("userId,movieId,rating\n2,10,1\n2,20,5\n9,10,4.5\n", encoding="utf-8")
        yield from original(*args)

    monkeypatch.setattr(preparation, "rating_chunks", changing)
    with pytest.raises(ValueError, match="Source changed"):
        preparation.prepare_movielens(source, source / "prepared")
    assert not (source / "prepared").exists()
    assert not list(source.glob(".staging-*"))
