"""Read-only numeric MovieLens profiles and movie-to-user postings."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np


FORMAT_VERSION = 1
ARRAY_DTYPES = {
    "user_ids": "int64", "user_offsets": "uint64",
    "profile_movie_indices": "uint32", "profile_ratings": "float64",
    "user_means": "float64", "movie_ids": "int64",
    "movie_offsets": "uint64", "posting_user_indices": "uint32",
    "movie_counts": "uint64", "movie_totals": "float64",
    "movie_averages": "float64", "popularity_order": "uint32",
}


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@dataclass(frozen=True)
class PreparedHistoricalData:
    arrays: dict[str, np.ndarray]
    catalog: dict
    manifest: dict

    def profile(self, user_index: int) -> tuple[np.ndarray, np.ndarray]:
        offsets = self.arrays["user_offsets"]
        start, end = int(offsets[user_index]), int(offsets[user_index + 1])
        return (self.arrays["profile_movie_indices"][start:end],
                self.arrays["profile_ratings"][start:end])

    def postings(self, movie_index: int) -> np.ndarray:
        offsets = self.arrays["movie_offsets"]
        return self.arrays["posting_user_indices"][int(offsets[movie_index]):int(offsets[movie_index + 1])]

    def user_index(self, user_id: int) -> int:
        ids = self.arrays["user_ids"]
        index = int(np.searchsorted(ids, user_id))
        if index == len(ids) or int(ids[index]) != user_id:
            raise KeyError(user_id)
        return index

    def movie_index(self, movie_id: int) -> int | None:
        ids = self.arrays["movie_ids"]
        index = int(np.searchsorted(ids, movie_id))
        return index if index < len(ids) and int(ids[index]) == movie_id else None

    @property
    def genres(self) -> dict[int, list[str]]:
        return {row["movie_id"]: row["genres"] for row in self.catalog["movies"]}

    @property
    def release_years(self) -> dict[int, int | None]:
        return {row["movie_id"]: row["release_year"] for row in self.catalog["movies"]}

    def close(self) -> None:
        """Release file mappings, including Windows locks on artifact files."""
        for array in self.arrays.values():
            array._mmap.close()


def load_prepared(directory: Path, *, verify: bool = False) -> PreparedHistoricalData:
    arrays = {}
    try:
        return _load_prepared(Path(directory), arrays, verify=verify)
    except Exception:
        for array in arrays.values():
            array._mmap.close()
        raise


def _load_prepared(directory: Path, arrays: dict, *, verify: bool) -> PreparedHistoricalData:
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest["format_version"] != FORMAT_VERSION:
        raise ValueError("Unsupported historical artifact format")
    catalog = json.loads((directory / "catalog.json").read_text(encoding="utf-8"))
    for name, dtype in ARRAY_DTYPES.items():
        array = np.load(directory / f"{name}.npy", mmap_mode="r", allow_pickle=False)
        arrays[name] = array
        if array.ndim != 1 or array.dtype != np.dtype(dtype) or list(array.shape) != manifest["arrays"][name]["shape"] or manifest["arrays"][name]["dtype"] != dtype:
            raise ValueError(f"Invalid array shape or dtype: {name}")
    users, movies, ratings = (manifest[key] for key in ("user_count", "movie_count", "rating_count"))
    lengths = {
        "user_ids": users, "user_offsets": users + 1, "user_means": users,
        "movie_ids": movies, "movie_offsets": movies + 1,
        "movie_counts": movies, "movie_totals": movies, "movie_averages": movies,
        "profile_movie_indices": ratings, "profile_ratings": ratings,
        "posting_user_indices": ratings,
    }
    if users < 1 or movies < 1 or ratings < 1 or any(len(arrays[name]) != length for name, length in lengths.items()):
        raise ValueError("Inconsistent artifact counts")
    for name in ("user_offsets", "movie_offsets"):
        if arrays[name][0] != 0 or arrays[name][-1] != ratings or np.any(arrays[name][1:] < arrays[name][:-1]):
            raise ValueError(f"Invalid offset endpoints: {name}")
    for name in ("user_ids", "movie_ids"):
        if np.any(arrays[name] <= 0) or np.any(arrays[name][1:] <= arrays[name][:-1]):
            raise ValueError(f"Invalid sorted IDs: {name}")
    if len(catalog["movies"]) != movies:
        raise ValueError("Inconsistent catalog count")
    if sorted(row["movie_id"] for row in catalog["movies"]) != arrays["movie_ids"].tolist():
        raise ValueError("Invalid catalog IDs")
    if not np.isfinite(manifest["global_mean"]) or not .5 <= manifest["global_mean"] <= 5:
        raise ValueError("Invalid global mean")
    if not np.all(np.isfinite(arrays["user_means"]) & (arrays["user_means"] >= .5) & (arrays["user_means"] <= 5)):
        raise ValueError("Invalid user means")
    data = PreparedHistoricalData(arrays, catalog, manifest)
    if verify:
        expected_files = {f"{name}.npy" for name in ARRAY_DTYPES} | {"catalog.json", "README.txt"}
        if set(manifest["artifact_checksums"]) != expected_files:
            data.close()
            raise ValueError("Incomplete artifact checksums")
        for filename, expected in manifest["artifact_checksums"].items():
            if checksum(directory / filename) != expected:
                data.close()
                raise ValueError(f"Artifact checksum mismatch: {filename}")
        try:
            verify_contents(data)
        except Exception:
            data.close()
            raise
    return data


def verify_contents(data: PreparedHistoricalData) -> None:
    """Explicit full index/statistics validation; bounded by one profile/posting."""
    a = data.arrays
    for name in ("user_ids", "movie_ids"):
        if np.any(a[name] <= 0) or np.any(a[name][1:] <= a[name][:-1]):
            raise ValueError(f"Invalid sorted IDs: {name}")
    for name in ("user_offsets", "movie_offsets"):
        if np.any(a[name][1:] < a[name][:-1]):
            raise ValueError(f"Invalid offsets: {name}")
    totals = np.zeros(len(a["movie_ids"]), dtype=np.float64)
    counts = np.zeros(len(totals), dtype=np.uint64)
    user_totals = []
    for user in range(len(a["user_ids"])):
        movies, ratings = data.profile(user)
        if not len(movies) or np.any(movies >= len(totals)) or np.any(movies[1:] <= movies[:-1]):
            raise ValueError("Invalid profile movie indexes")
        if not np.all(np.isfinite(ratings) & (ratings >= .5) & (ratings <= 5)):
            raise ValueError("Invalid prepared ratings")
        total = sum(float(rating) for rating in ratings)
        user_totals.append(total)
        if total / len(ratings) != float(a["user_means"][user]):
            raise ValueError("Invalid user mean")
        for movie, rating in zip(movies, ratings):
            totals[int(movie)] += float(rating)
            counts[int(movie)] += 1
    if not np.array_equal(totals, a["movie_totals"]) or not np.array_equal(counts, a["movie_counts"]):
        raise ValueError("Invalid movie statistics")
    for movie in range(len(totals)):
        postings = data.postings(movie)
        if len(postings) != counts[movie] or np.any(postings >= len(a["user_ids"])) or np.any(postings[1:] <= postings[:-1]):
            raise ValueError("Invalid movie postings")
        for user in postings:
            profile, _ = data.profile(int(user))
            position = int(np.searchsorted(profile, movie))
            if position == len(profile) or int(profile[position]) != movie:
                raise ValueError("Posting does not match profile")
    averages = np.divide(totals, counts, out=np.zeros_like(totals), where=counts > 0)
    order = sorted((i for i in range(len(totals)) if counts[i]),
                   key=lambda i: (-float(averages[i]), -int(counts[i]), int(a["movie_ids"][i])))
    if not np.array_equal(averages, a["movie_averages"]) or not np.array_equal(order, a["popularity_order"]):
        raise ValueError("Invalid popularity statistics")
    total = sum(user_totals)
    if total != data.manifest["global_rating_total"] or total / len(a["profile_ratings"]) != data.manifest["global_mean"]:
        raise ValueError("Invalid global statistics")
    if sorted(row["movie_id"] for row in data.catalog["movies"]) != a["movie_ids"].tolist():
        raise ValueError("Invalid catalog IDs")
    from app.recommender import available_decades, release_year
    genres = {}
    decades = {}
    years = {}
    for row in data.catalog["movies"]:
        if not isinstance(row["title"], str) or not row["title"].strip() or not row["genres"] or any(not isinstance(g, str) for g in row["genres"]):
            raise ValueError("Invalid catalog metadata")
        year = release_year(row["title"])
        if year != row["release_year"]:
            raise ValueError("Invalid release year")
        years[row["movie_id"]] = year
        for genre in set(g.casefold() for g in row["genres"]):
            genres.setdefault(genre, []).append(row["movie_id"])
        if year is not None:
            decades.setdefault(str(year // 10 * 10), []).append(row["movie_id"])
    if (data.catalog["decades"] != available_decades(years)
            or data.catalog["genre_movies"] != {g: sorted(ids) for g, ids in genres.items()}
            or data.catalog["decade_movies"] != {d: sorted(ids) for d, ids in decades.items()}):
        raise ValueError("Invalid catalog membership")
