"""Compare the independent exhaustive oracle with prepared historical access."""

from dataclasses import asdict
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app import recommender as new
from app.data import load_movielens
from app.historical import load_prepared
from scripts.prepare_movielens import prepare_movielens
import reference_recommender as old


def previous_overlap_counts(target, prepared, excluded=None):
    """Frozen pre-optimization indexed counting, independent of new helpers."""
    counts = {}
    for movie in sorted(target):
        movie_index = prepared.movie_index(movie)
        if movie_index is None:
            continue
        for index in prepared.postings(movie_index):
            user = int(index)
            if int(prepared.arrays["user_ids"][user]) != excluded:
                counts[user] = counts.get(user, 0) + 1
    return counts


def previous_shared_profile(target, prepared, user):
    movies, ratings = prepared.profile(user)
    shared = {}
    for movie in sorted(target):
        movie_index = prepared.movie_index(movie)
        if movie_index is None:
            continue
        position = int(np.searchsorted(movies, movie_index))
        if position < len(movies) and int(movies[position]) == movie_index:
            shared[movie] = float(ratings[position])
    return shared


def previous_batched_shared_ratings(mapped, indices, arrays, user):
    """Frozen first-optimization lookup, independent of runtime helpers."""
    offsets = arrays["user_offsets"]
    start, end = int(offsets[user]), int(offsets[user + 1])
    movies = arrays["profile_movie_indices"][start:end]
    ratings = arrays["profile_ratings"][start:end]
    positions = np.searchsorted(movies, indices)
    return {movie: float(ratings[position]) for movie, index, position in zip(mapped, indices, positions)
            if position < len(movies) and movies[position] == index}


def previous_masked_shared_ratings(mapped, indices, arrays, user):
    """Frozen second-optimization lookup, independent of runtime helpers."""
    offsets = arrays["user_offsets"]
    start, end = int(offsets[user]), int(offsets[user + 1])
    movies = arrays["profile_movie_indices"][start:end]
    ratings = arrays["profile_ratings"][start:end]
    positions = np.searchsorted(movies, indices)
    valid = np.flatnonzero(positions < len(movies))
    matched = valid[movies[positions[valid]] == indices[valid]]
    shared_ratings = ratings[positions[matched]].tolist()
    return dict(zip((mapped[int(index)] for index in matched), shared_ratings))


def exact_values(value):
    """Compare float representations, including signed zero, recursively."""
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {key: exact_values(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [exact_values(item) for item in value]
    return value


def compare_indexed(target, prepared, **settings):
    overlap = settings.get("min_overlap", 2)
    excluded = settings.get("exclude_user_id")
    counts = previous_overlap_counts(target, prepared, excluded)
    assert new.indexed_overlap_counts(target, prepared, excluded) == counts
    arrays = {name: np.asarray(array) for name, array in prepared.arrays.items()}
    mapped, indices = new._mapped_target(target, prepared)
    dense = new._dense_overlap_counts(indices, arrays, excluded)
    eligible = {user for user, count in counts.items() if count >= overlap}
    assert set(map(int, np.flatnonzero(dense >= overlap))) == eligible
    positives = []
    for user in sorted(eligible):
        previous = previous_shared_profile(target, prepared, user)
        actual = new._shared_ratings(mapped, indices, arrays, user)
        batched = previous_batched_shared_ratings(mapped, indices, arrays, user)
        masked = previous_masked_shared_ratings(mapped, indices, arrays, user)
        assert list(actual) == list(batched) == list(masked) == list(previous)
        assert all(type(value) is float for value in actual.values())
        assert exact_values(actual) == exact_values(batched)
        assert exact_values(actual) == exact_values(masked)
        assert exact_values(actual) == exact_values(previous)
        expected_similarity = old.pearson_similarity(target, previous, overlap)
        similarity = new.pearson_similarity(target, actual, overlap)
        assert similarity.hex() == expected_similarity.hex()
        assert (similarity > 0, similarity == 0) == (expected_similarity > 0, expected_similarity == 0)
        if expected_similarity > 0:
            shared_count = len(previous)
            weighted = expected_similarity * shared_count / (shared_count + old.PEARSON_SHRINKAGE)
            positives.append((int(arrays["user_ids"][user]), weighted))
    positives.sort(key=lambda neighbor: (-neighbor[1], neighbor[0]))
    assert exact_values(new.indexed_neighbors(target, prepared, len(arrays["user_ids"]), overlap, excluded)) == exact_values(positives)
    selected = positives[:settings.get("k", 15)]
    assert exact_values(new.nearest_neighbors(target, prepared, settings.get("k", 15), overlap, excluded)) == exact_values(selected)
    actual = new.recommend_details(target, prepared, genres=prepared.genres, **settings)
    # Replay downstream with independently calculated weighted neighbors.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(new, "nearest_neighbors", lambda *args, **kwargs: selected)
        expected = new.recommend_details(target, prepared, genres=prepared.genres, **settings)
    assert exact_values([asdict(row) for row in actual]) == exact_values([asdict(row) for row in expected])
    assert exact_values({movie: asdict(row) for movie, row in new.predict_ratings_with_confidence(
        target, prepared, selected, settings.get("min_neighbors", 1), settings.get("allowed_movies"),
    ).items()}) == exact_values({movie: asdict(row) for movie, row in old.predict_ratings_with_confidence(
        target, {user: {int(arrays["movie_ids"][int(movie)]): float(rating)
                      for movie, rating in zip(*prepared.profile(prepared.user_index(user)))} for user, _ in selected},
        selected, settings.get("min_neighbors", 1), settings.get("allowed_movies"),
    ).items()})


def write_source(path, profiles, catalog=None):
    movie_ids = sorted({movie for profile in profiles.values() for movie in profile})
    if catalog is None:
        catalog = [(movie, f"Film ({1999 + movie % 3})", "Action|Drama" if movie % 2 else "Sci-Fi") for movie in movie_ids]
    pd.DataFrame(catalog, columns=["movieId", "title", "genres"]).to_csv(path / "movies.csv", index=False)
    pd.DataFrame([(user, movie, rating) for user, profile in sorted(profiles.items()) for movie, rating in sorted(profile.items())],
                 columns=["userId", "movieId", "rating"]).to_csv(path / "ratings.csv", index=False)
    (path / "README.txt").write_text("Synthetic test data", encoding="utf-8")


def compare(target, movies, users, prepared, **settings):
    compare_indexed(target, prepared, **settings)
    k, overlap, excluded = (settings.get(name, default) for name, default in (("k", 15), ("min_overlap", 2), ("exclude_user_id", None)))
    counts = new.indexed_overlap_counts(target, prepared, excluded)
    actual_counts = {int(prepared.arrays["user_ids"][i]): count for i, count in counts.items()}
    expected_counts = {user: len(target.keys() & profile.keys()) for user, profile in users.items()
                       if user != excluded and target.keys() & profile.keys()}
    assert actual_counts == expected_counts
    eligible = {user for user, count in expected_counts.items() if count >= overlap}
    assert {user for user, count in actual_counts.items() if count >= overlap} == eligible
    for user in users:
        assert new.pearson_similarity(target, new.shared_profile(target, prepared, prepared.user_index(user)), overlap) == old.pearson_similarity(target, users[user], overlap)
    expected_neighbors = old.nearest_neighbors(target, users, k, overlap, excluded)
    assert new.nearest_neighbors(target, prepared, k, overlap, excluded) == expected_neighbors
    allowed = settings.get("allowed_movies")
    support = settings.get("min_neighbors", 1)
    expected_predictions = old.predict_ratings_with_confidence(target, users, expected_neighbors, support, allowed)
    actual_predictions = new.predict_ratings_with_confidence(target, prepared, expected_neighbors, support, allowed)
    assert {movie: asdict(value) for movie, value in actual_predictions.items()} == {movie: asdict(value) for movie, value in expected_predictions.items()}
    assert [asdict(row) for row in new.recommend_details(target, prepared, genres=prepared.genres, **settings)] == [
        asdict(row) for row in old.recommend_details(target, users, genres=prepared.genres, **settings)]
    for minimum in (1, 2, 20):
        assert new.popular_recommendations(prepared, min_rating_count=minimum, exclude_movies=target, allowed_movies=allowed) == old.popular_recommendations(users, min_rating_count=minimum, exclude_movies=target, allowed_movies=allowed)
        for genre in ("Action", " sci-fi ", "Drama", "Unknown", "Sci", "(no genres listed)"):
            assert new.genre_recommendations(genre, None, prepared, min_rating_count=minimum, exclude_movies=target, allowed_movies=allowed) == old.genre_recommendations(genre, movies, users, min_rating_count=minimum, exclude_movies=target, allowed_movies=allowed)


@pytest.fixture
def synthetic(tmp_path):
    profiles = {
        1: {1: 1., 2: 2., 3: 3., 4: 5., 5: .5},
        2: {1: 2., 2: 3., 3: 4., 4: 2., 6: 5.},
        3: {1: 5., 2: 4., 3: 3., 4: 3.},
        4: {1: 3., 2: 3., 3: 3., 7: 5.},
        5: {1: 1., 8: 5.},
        6: {8: 4., 9: 4.},
    }
    profiles.update({user: {1: 2., 2: 3., 3: 4., 4: 5., 6: 4.} for user in range(10, 30)})
    write_source(tmp_path, profiles)
    movies, ratings = load_movielens(tmp_path)
    path = prepare_movielens(tmp_path, tmp_path / "prepared", chunk_size=2)
    return movies, old.build_user_ratings(ratings), load_prepared(path, verify=True)


@pytest.mark.parametrize("target", [{}, {1: 5.}, {1: 1., 2: 2., 3: 3.}, {1: 5., 2: 4., 3: 3.},
                                    {1: 3., 2: 3., 3: 3.}, {90: 1., 91: 5.},
                                    {1: 3., 2: 3. + 1e-8, 3: 3. - 1e-8}])
@pytest.mark.parametrize("settings", [{}, {"k": 1}, {"k": 40, "min_overlap": 3}, {"min_overlap": 4},
                                      {"min_neighbors": 2}, {"min_neighbors": 30}, {"exclude_user_id": 1},
                                      {"allowed_movies": set()}, {"allowed_movies": {4, 6, 8}},
                                      {"rank_by_confidence": False}, {"genre_weight": 0}, {"limit": 0}])
def test_synthetic_equivalence(synthetic, target, settings):
    compare(target, *synthetic, **settings)


def test_hand_calculated_predictions_and_ties(tmp_path):
    users = {1: {1: 1., 2: 3., 3: 5.}, 2: {1: 1., 2: 3., 3: 2., 4: 4.}}
    write_source(tmp_path, users)
    data = load_prepared(prepare_movielens(tmp_path, tmp_path / "prepared"))
    target = {1: 2., 2: 4.}
    predictions = new.predict_ratings_with_confidence(target, data, [(1, 1.), (2, .5), (1, .9)])
    assert predictions[3].raw_score == 3 + (.6 / 5.6) * ((2 - .25) / 1.5)
    assert predictions[4].score == 3 + (.2 / 5.2) * 1.5
    assert predictions[3].confidence == pytest.approx(.6 / 3.6)
    assert new.nearest_neighbors(target, data, k=1) == [(1, 2 / 12)]


def test_fractional_constant_group_and_tiny_historical_variation(tmp_path):
    target = old.combine_profiles([dict.fromkeys(range(1, 26), rating) for rating in (.5, .5, 1.)])
    users = {1: dict.fromkeys(range(1, 26), 2 / 3),
             2: {movie: 3. + (movie % 3 - 1) * 1e-8 for movie in range(1, 26)}}
    write_source(tmp_path, users)
    movies, ratings = load_movielens(tmp_path)
    # Compare the actual parsed float values, as normal runtime does.
    compare(target, movies, old.build_user_ratings(ratings), load_prepared(prepare_movielens(tmp_path, tmp_path / "prepared")))


@pytest.mark.parametrize("target,users", [
    ({1: 4., 2: 5.}, {1: {1: 1., 2: 2., 3: 4., 4: 5.}}),
    ({1: .5, 2: 1.}, {1: {1: 4., 2: 5., 3: .5, 4: 1.}}),
    ({1: 1., 2: 5.}, {1: {1: 1., 2: 5., 3: 4.}, 2: {3: 2.}}),
    ({}, {1: {1: 4., 2: 4., 3: 4., 4: 5.}, 2: {2: 4., 3: 4.}}),
])
def test_clipping_support_and_popularity_order(tmp_path, target, users):
    write_source(tmp_path, users)
    movies, ratings = load_movielens(tmp_path)
    prepared = load_prepared(prepare_movielens(tmp_path, tmp_path / "prepared"))
    parsed = old.build_user_ratings(ratings)
    for settings in ({}, {"rank_by_confidence": False}, {"min_neighbors": 2}):
        compare(target, movies, parsed, prepared, **settings)
    if target == {1: 4., 2: 5.}:
        rows = new.recommend_details(target, prepared)
        assert [row.movie_id for row in rows] == [4, 3]
        assert all(4.5 < row.score < 5 for row in rows)
        assert new.recommend(target, prepared) == [(row.movie_id, row.score) for row in rows]


def test_group_combination_and_unpadded_output(synthetic):
    profiles = [{1: 1., 2: 5.}, {2: 3., 3: 4.}, {}]
    assert new.combine_profiles(profiles) == old.combine_profiles(profiles) == {1: 1., 2: 4., 3: 4.}
    compare(new.combine_profiles(profiles), *synthetic)
    compare(new.combine_profiles([{}, {}]), *synthetic)


def test_decimal_historical_statistics(tmp_path):
    users = {1: {1: .6666666666666666, 2: 3.0000000000000004, 3: 3.1234567890123456},
             2: {1: .5000000000000001, 2: 4.999999999999999, 3: 2.1234567890123456}}
    write_source(tmp_path, users)
    movies, ratings = load_movielens(tmp_path)
    compare({1: 1., 2: 5.}, movies, old.build_user_ratings(ratings), load_prepared(prepare_movielens(tmp_path, tmp_path / "prepared")))


@pytest.fixture(scope="module")
def small(tmp_path_factory):
    source = Path(__file__).resolve().parents[1] / "data"
    movies, ratings = load_movielens(source)
    path = prepare_movielens(source, tmp_path_factory.mktemp("small") / "prepared", chunk_size=4096)
    return movies, old.build_user_ratings(ratings), load_prepared(path, verify=True)


@pytest.mark.parametrize("case", range(16))
def test_latest_small_equivalence(small, case):
    movies, users, prepared = small
    user = (1, 7, 19, 68, 111, 232, 414, 610)[case % 8]
    profile = users[user]
    size = (0, 1, 5, 20)[case % 4]
    target = dict(list(profile.items())[:size])
    if case >= 8:
        target = old.combine_profiles([target, dict(list(users[1 + case].items())[:12])])
    allowed = new.movie_ids_for_decade(prepared.release_years, (None, 1990, 2000, 1800)[case % 4])
    compare(target, movies, users, prepared, allowed_movies=allowed, exclude_user_id=user if case < 8 else None,
            min_neighbors=1 + case % 2, min_overlap=2 + case % 2, k=(1, 15, 30)[case % 3])


def test_latest_small_full_profile_and_popular_movies(small):
    movies, users, prepared = small
    compare(users[414], movies, users, prepared, exclude_user_id=414)
    popular = sorted(prepared.arrays["popularity_order"], key=lambda i: -int(prepared.arrays["movie_counts"][i]))[:10]
    target = {int(prepared.arrays["movie_ids"][i]): .5 + position % 10 * .5 for position, i in enumerate(popular)}
    compare(target, movies, users, prepared)
    assert np.array_equal(prepared.arrays["user_ids"], sorted(users))


@pytest.mark.parametrize("call", [lambda data: new.nearest_neighbors({}, data, k=0),
                                 lambda data: new.nearest_neighbors({}, data, min_overlap=1),
                                 lambda data: new.predict_ratings({}, data, [], min_neighbors=0),
                                 lambda data: new.popular_recommendations(data, min_rating_count=0)])
def test_prepared_parameter_validation(synthetic, call):
    with pytest.raises(ValueError):
        call(synthetic[2])


def test_batched_lookup_boundaries_and_readonly_views(synthetic):
    prepared = synthetic[2]
    arrays = {name: np.asarray(array) for name, array in prepared.arrays.items()}
    assert all(np.shares_memory(array, prepared.arrays[name]) and not array.flags.writeable
               for name, array in arrays.items())
    for target in ({-1: 1., 1: 2., 9: 4., 10000: 5.}, {90: 1., 91: 5.}):
        compare_indexed(target, prepared, exclude_user_id=999999)
    empty = dict(arrays)
    empty["user_offsets"] = np.array([0, 0], dtype=np.uint64)
    empty["profile_movie_indices"] = np.array([], dtype=np.uint32)
    empty["profile_ratings"] = np.array([], dtype=np.float64)
    assert new._shared_ratings([1], np.array([0], dtype=np.uint32), empty, 0) == {}


@pytest.mark.parametrize("extra_targets", [0, 50])
@pytest.mark.parametrize("indices", [[], [0, 2, 4], [1, 3, 5], [0, 1, 2, 3, 4, 5]])
@pytest.mark.parametrize("movies,ratings", [([], []), ([0, 2, 4], [.5, 2 / 3, 5.]),
                                           ([2], [3.0000000000000004])])
def test_masked_lookup_exact_matches_and_order(indices, movies, ratings, extra_targets):
    arrays = {
        "user_offsets": np.array([0, len(movies)], dtype=np.uint64),
        "profile_movie_indices": np.array(movies, dtype=np.uint32),
        "profile_ratings": np.array(ratings, dtype=np.float64),
    }
    indices = np.array(indices + list(range(6, 6 + extra_targets)), dtype=np.uint32)
    mapped = [100 + int(index) for index in indices]
    expected = previous_batched_shared_ratings(mapped, indices, arrays, 0)
    masked = previous_masked_shared_ratings(mapped, indices, arrays, 0)
    actual = new._shared_ratings(mapped, indices, arrays, 0)
    assert list(actual) == list(expected) == list(masked)
    assert all(type(value) is float for value in actual.values())
    assert exact_values(actual) == exact_values(expected)
    assert exact_values(actual) == exact_values(masked)


@pytest.mark.parametrize("mapped_count", [49, 50, 51])
def test_hybrid_uses_known_mapped_count(tmp_path, mapped_count):
    profiles = {1: {movie: .5 + movie % 10 * .5 for movie in range(1, 52)},
                2: {movie: 3. + (movie % 3 - 1) * 1e-8 for movie in range(1, 52, 2)}}
    write_source(tmp_path, profiles)
    prepared = load_prepared(prepare_movielens(tmp_path, tmp_path / "prepared"))
    try:
        target = {movie: profiles[1][movie] for movie in range(1, mapped_count + 1)}
        target.update({-1: 1., 10000: 5.})
        mapped, indices = new._mapped_target(target, prepared)
        assert len(target) == mapped_count + 2
        assert len(indices) == mapped_count
        arrays = {name: np.asarray(array) for name, array in prepared.arrays.items()}
        expected = previous_batched_shared_ratings(mapped, indices, arrays, 0)
        masked = previous_masked_shared_ratings(mapped, indices, arrays, 0)
        calls = []
        original = np.flatnonzero
        def track_mask(values):
            calls.append(len(values))
            return original(values)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(new.np, "flatnonzero", track_mask)
            actual = new._shared_ratings(mapped, indices, arrays, 0)
        assert calls == ([] if mapped_count < 50 else [mapped_count])
        assert list(actual) == list(expected) == list(masked)
        assert exact_values(actual) == exact_values(expected) == exact_values(masked)
        compare_indexed(target, prepared)
    finally:
        prepared.close()


@pytest.mark.skipif(not os.environ.get("MOVIELENS_32M_EQUIVALENCE"), reason="Opt-in local 32M equivalence")
@pytest.mark.parametrize("case", ["small_5", "popular_5", "medium_20", "group", "large_50", "large_75", "large_100", "decade_2010"])
def test_32m_indexed_equivalence(case):
    prepared = load_prepared(Path(__file__).resolve().parents[1] / "data/prepared/ml-32m-v1")
    try:
        eligible = np.flatnonzero(np.diff(prepared.arrays["user_offsets"]) >= 100)
        def profile(index, count):
            movies, ratings = prepared.profile(int(index))
            return {int(prepared.arrays["movie_ids"][int(movie)]): float(rating)
                    for movie, rating in zip(movies[:count], ratings[:count])}
        full = profile(eligible[0], 100)
        targets = {"small_5": dict(list(full.items())[:5]), "medium_20": dict(list(full.items())[:20]),
                   "large_50": dict(list(full.items())[:50]), "large_75": dict(list(full.items())[:75]), "large_100": full}
        popular = sorted(range(len(prepared.arrays["movie_ids"])),
                         key=lambda index: (-int(prepared.arrays["movie_counts"][index]), int(prepared.arrays["movie_ids"][index])))[:5]
        targets["popular_5"] = {int(prepared.arrays["movie_ids"][index]): rating
                                for index, rating in zip(popular, (1., 2., 3., 4., 5.))}
        targets["group"] = old.combine_profiles([targets["medium_20"], profile(eligible[1], 20)])
        targets["decade_2010"] = targets["medium_20"]
        settings = {"allowed_movies": new.movie_ids_for_decade(prepared.release_years, 2010)} if case == "decade_2010" else {}
        compare_indexed(targets[case], prepared, **settings)
    finally:
        prepared.close()
