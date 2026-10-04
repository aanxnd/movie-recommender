import json

import numpy as np
import pytest

from app.historical import load_prepared, verify_contents
from scripts.prepare_movielens import prepare_movielens


@pytest.fixture
def artifacts(tmp_path):
    (tmp_path / "movies.csv").write_text("movieId,title,genres\n1,A,Drama\n2,B,Action\n", encoding="utf-8")
    (tmp_path / "ratings.csv").write_text("userId,movieId,rating\n1,1,1\n1,2,5\n2,1,4\n", encoding="utf-8")
    (tmp_path / "README.txt").write_text("Terms", encoding="utf-8")
    return prepare_movielens(tmp_path, tmp_path / "prepared")


def test_missing_and_incompatible_version(artifacts):
    path = artifacts / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["format_version"] = 999
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Unsupported"):
        load_prepared(artifacts)
    with pytest.raises(FileNotFoundError):
        load_prepared(artifacts / "missing")


@pytest.mark.parametrize("name,values,dtype", [
    ("user_offsets", [0, 2, 4], "uint64"),
    ("user_ids", [1, 2], "uint32"),
    ("profile_ratings", [1, 5], "float64"),
])
def test_structural_validation(artifacts, name, values, dtype):
    np.save(artifacts / f"{name}.npy", np.array(values, dtype=dtype))
    with pytest.raises(ValueError):
        load_prepared(artifacts)


def test_checksum_validation(artifacts):
    (artifacts / "README.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        load_prepared(artifacts, verify=True)


@pytest.mark.parametrize("name,values,dtype", [
    ("posting_user_indices", [0, 0, 0], "uint32"),
    ("profile_movie_indices", [0, 0, 0], "uint32"),
    ("user_means", [4, 4], "float64"),
    ("movie_totals", [6, 5], "float64"),
    ("movie_averages", [3, 5], "float64"),
    ("popularity_order", [0, 1], "uint32"),
])
def test_full_validation_detects_inconsistent_contents(artifacts, name, values, dtype):
    np.save(artifacts / f"{name}.npy", np.array(values, dtype=dtype))
    data = load_prepared(artifacts)
    with pytest.raises(ValueError):
        verify_contents(data)


def test_metadata_and_checksum_inventory(artifacts):
    path = artifacts / "catalog.json"
    catalog = json.loads(path.read_text())
    catalog["genre_movies"]["drama"] = [2]
    path.write_text(json.dumps(catalog))
    data = load_prepared(artifacts)
    with pytest.raises(ValueError, match="membership"):
        verify_contents(data)
    data.close()
    path = artifacts / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["artifact_checksums"].pop("README.txt")
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Incomplete"):
        load_prepared(artifacts, verify=True)
