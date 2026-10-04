"""Prepare existing ordered MovieLens CSVs offline; never download data."""

import argparse
import csv
from contextlib import ExitStack
from decimal import Decimal, InvalidOperation
import json
from math import isfinite
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.historical import ARRAY_DTYPES, FORMAT_VERSION, checksum, load_prepared
from app.recommender import available_decades, release_year


def positive_id(value: str) -> int:
    try:
        number = Decimal(value)
        if not number.is_finite() or number <= 0 or number != number.to_integral_value():
            raise ValueError("IDs must be positive integers")
        if number > 2**63 - 1:
            raise ValueError("IDs must fit in signed int64")
        return int(number)
    except (InvalidOperation, TypeError) as error:
        raise ValueError("IDs must be positive integers") from error


def rows(path: Path, columns: tuple[str, ...]):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = set(columns) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
        found = False
        for row in reader:
            found = True
            yield tuple(row[column] for column in columns)
        if not found:
            raise ValueError(f"{path.name}: data must be nonempty")


def rating_chunks(path: Path, movie_indexes: dict[int, int], chunk_size: int):
    """Stream required values only, retaining ordering checks across chunks."""
    previous = None
    chunk = []
    for raw_user, raw_movie, raw_rating in rows(path, ("userId", "movieId", "rating")):
        user, movie = positive_id(raw_user), positive_id(raw_movie)
        pair = user, movie
        if pair == previous:
            raise ValueError("ratings.csv: duplicate user/movie pairs")
        if previous is not None and pair < previous:
            raise ValueError("ratings.csv must be ordered by userId then movieId")
        previous = pair
        if movie not in movie_indexes:
            raise ValueError("ratings.csv: rating references an unknown movie")
        try:
            rating = float(raw_rating)
        except (TypeError, ValueError) as error:
            raise ValueError("ratings.csv: invalid rating") from error
        if not isfinite(rating) or not .5 <= rating <= 5:
            raise ValueError("ratings.csv: ratings must be finite between 0.5 and 5.0")
        chunk.append((user, movie_indexes[movie], rating))
        if len(chunk) == chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def prepare_movielens(source: Path, destination: Path, *, dataset: str = "latest-small", chunk_size: int = 100_000) -> Path:
    """Two source passes; memory is O(chunk size + users + catalog), not ratings."""
    source, destination = Path(source), Path(destination)
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    if destination.exists():
        raise FileExistsError(f"Prepared destination already exists: {destination}")
    sources = {name: checksum(source / name) for name in ("movies.csv", "ratings.csv", "README.txt")}
    catalog_rows = []
    seen = set()
    for raw_movie, title, genres in rows(source / "movies.csv", ("movieId", "title", "genres")):
        movie = positive_id(raw_movie)
        if movie in seen:
            raise ValueError("movies.csv: duplicate movie IDs")
        if not title or not title.strip() or not genres or not genres.strip():
            raise ValueError("movies.csv: title and genres must contain nonempty text")
        seen.add(movie)
        catalog_rows.append({"movie_id": movie, "title": title, "genres": genres.split("|"), "release_year": release_year(title)})
    movie_ids = np.array(sorted(seen), dtype=np.int64)
    if len(movie_ids) > np.iinfo(np.uint32).max:
        raise ValueError("Movie cardinality exceeds uint32 indexes")
    movie_indexes = {int(movie): i for i, movie in enumerate(movie_ids)}
    user_ids, user_counts = [], []
    movie_counts = np.zeros(len(movie_ids), dtype=np.uint64)
    movie_totals = np.zeros(len(movie_ids), dtype=np.float64)
    for chunk in rating_chunks(source / "ratings.csv", movie_indexes, chunk_size):
        for user, movie, rating in chunk:
            if not user_ids or user != user_ids[-1]:
                user_ids.append(user)
                user_counts.append(0)
            user_counts[-1] += 1
            movie_counts[movie] += 1
            movie_totals[movie] += rating
    if len(user_ids) > np.iinfo(np.uint32).max:
        raise ValueError("User cardinality exceeds uint32 indexes")
    user_offsets = np.concatenate((np.zeros(1, dtype=np.uint64), np.cumsum(user_counts, dtype=np.uint64)))
    movie_offsets = np.concatenate((np.zeros(1, dtype=np.uint64), np.cumsum(movie_counts, dtype=np.uint64)))
    rating_count = int(user_offsets[-1])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".staging-", dir=destination.parent) as temporary, ExitStack() as mapped:
        staging = Path(temporary)
        large = {}
        for name in ("profile_movie_indices", "profile_ratings", "posting_user_indices"):
            large[name] = np.lib.format.open_memmap(staging / f"{name}.npy", mode="w+", dtype=ARRAY_DTYPES[name], shape=(rating_count,))
            mapped.callback(large[name]._mmap.close)
        cursors = movie_offsets[:-1].copy()
        user_index = -1
        previous_user = None
        position = 0
        for chunk in rating_chunks(source / "ratings.csv", movie_indexes, chunk_size):
            for user, movie, rating in chunk:
                if user != previous_user:
                    user_index += 1
                    previous_user = user
                    if user_index >= len(user_ids) or user != user_ids[user_index] or position != int(user_offsets[user_index]):
                        raise ValueError("Source changed between preparation passes")
                if position >= rating_count or int(cursors[movie]) >= int(movie_offsets[movie + 1]):
                    raise ValueError("Source changed between preparation passes")
                large["profile_movie_indices"][position] = movie
                large["profile_ratings"][position] = rating
                large["posting_user_indices"][int(cursors[movie])] = user_index
                cursors[movie] += 1
                position += 1
        if position != rating_count or sources != {name: checksum(source / name) for name in sources}:
            raise ValueError("Source changed between preparation passes")
        user_totals = [sum(float(rating) for rating in large["profile_ratings"][int(start):int(end)])
                       for start, end in zip(user_offsets[:-1], user_offsets[1:])]
        averages = np.divide(movie_totals, movie_counts, out=np.zeros_like(movie_totals), where=movie_counts > 0)
        order = sorted((i for i in range(len(movie_ids)) if movie_counts[i]),
                       key=lambda i: (-float(averages[i]), -int(movie_counts[i]), int(movie_ids[i])))
        small = {
            "user_ids": user_ids, "user_offsets": user_offsets,
            "user_means": [total / count for total, count in zip(user_totals, user_counts)],
            "movie_ids": movie_ids, "movie_offsets": movie_offsets,
            "movie_counts": movie_counts, "movie_totals": movie_totals,
            "movie_averages": averages, "popularity_order": order,
        }
        for name, values in small.items():
            np.save(staging / f"{name}.npy", np.asarray(values, dtype=ARRAY_DTYPES[name]), allow_pickle=False)
        for array in large.values():
            array.flush()
        mapped.close()
        years = {row["movie_id"]: row["release_year"] for row in catalog_rows}
        genre_movies = {}
        decade_movies = {}
        for row in catalog_rows:
            for genre in set(token.casefold() for token in row["genres"]):
                genre_movies.setdefault(genre, []).append(row["movie_id"])
            if row["release_year"] is not None:
                decade_movies.setdefault(str(row["release_year"] // 10 * 10), []).append(row["movie_id"])
        write_json(staging / "catalog.json", {
            "movies": catalog_rows, "decades": available_decades(years),
            "genre_movies": {genre: sorted(ids) for genre, ids in genre_movies.items()},
            "decade_movies": {decade: sorted(ids) for decade, ids in decade_movies.items()},
        })
        shutil.copyfile(source / "README.txt", staging / "README.txt")
        manifest = {
            "format_version": FORMAT_VERSION, "preprocessor_version": 1,
            "dataset": dataset, "source_checksums": sources,
            "source_url": {"latest-small": "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip",
                           "ml-32m": "https://files.grouplens.org/datasets/movielens/ml-32m.zip"}.get(dataset),
            "dataset_version": "source SHA-256 checksums identify the imported snapshot",
            "user_count": len(user_ids), "movie_count": len(movie_ids), "rating_count": rating_count,
            "global_rating_total": sum(user_totals), "global_mean": sum(user_totals) / rating_count,
            "arrays": {name: {"dtype": dtype, "shape": list(np.load(staging / f"{name}.npy", mmap_mode="r").shape)} for name, dtype in ARRAY_DTYPES.items()},
            "artifact_checksums": {path.name: checksum(path) for path in sorted(staging.iterdir())},
        }
        write_json(staging / "manifest.json", manifest)
        checked = load_prepared(staging, verify=True)
        checked.close()
        staging.rename(destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("data/prepared/latest-small-v1"))
    parser.add_argument("--dataset", default="latest-small")
    parser.add_argument("--chunk-size", type=int, default=100_000)
    parser.add_argument("--verify", type=Path, help="Verify an existing artifact directory instead of preparing")
    args = parser.parse_args()
    try:
        if args.verify:
            data = load_prepared(args.verify, verify=True)
            print(f"Verified {data.manifest['rating_count']:,} ratings")
        else:
            print(prepare_movielens(args.source, args.output, dataset=args.dataset, chunk_size=args.chunk_size))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Preparation failed: {error}\n")


if __name__ == "__main__":
    main()
