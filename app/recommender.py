"""Readable user-user collaborative filtering over validated MovieLens data."""

from collections.abc import Iterable, Mapping
from math import sqrt

import pandas as pd


Profile = Mapping[int, float]
UserRatings = Mapping[int, Profile]
Neighbor = tuple[int, float]
Recommendation = tuple[int, float]


def build_user_ratings(ratings: pd.DataFrame) -> dict[int, dict[int, float]]:
    """Convert the loader's normalized historical ratings to sparse profiles."""
    users: dict[int, dict[int, float]] = {}
    for row in ratings.itertuples(index=False):
        users.setdefault(int(row.user_id), {})[int(row.movie_id)] = float(row.rating)
    return users


def pearson_similarity(first: Profile, second: Profile, min_overlap: int = 2) -> float:
    """Center on shared movies only; undefined correlations return zero."""
    if min_overlap < 2:
        raise ValueError("min_overlap must be at least 2")
    shared = sorted(first.keys() & second.keys())
    if len(shared) < min_overlap:
        return 0.0
    first_mean = sum(first[movie] for movie in shared) / len(shared)
    second_mean = sum(second[movie] for movie in shared) / len(shared)
    numerator = 0.0
    first_variance = 0.0
    second_variance = 0.0
    for movie in shared:
        first_difference = first[movie] - first_mean
        second_difference = second[movie] - second_mean
        numerator += first_difference * second_difference
        first_variance += first_difference ** 2
        second_variance += second_difference ** 2
    # Treat standard deviations <= 1e-12 rating units as rounding noise.
    variance_tolerance = len(shared) * 1e-24
    if first_variance <= variance_tolerance or second_variance <= variance_tolerance:
        return 0.0
    denominator = sqrt(first_variance * second_variance)
    return max(-1.0, min(1.0, numerator / denominator))


def nearest_neighbors(
    target: Profile,
    users: UserRatings,
    k: int = 15,
    min_overlap: int = 2,
    exclude_user_id: int | None = None,
) -> list[Neighbor]:
    """Keep positive correlations, descending, with user ID breaking ties.

    Pass exclude_user_id when the target is itself a historical MovieLens user.
    Application user IDs belong to a separate namespace and need no exclusion.
    """
    if k < 1 or min_overlap < 2:
        raise ValueError("k must be positive and min_overlap must be at least 2")
    neighbors = []
    for user_id, profile in users.items():
        if user_id == exclude_user_id:
            continue
        similarity = pearson_similarity(target, profile, min_overlap)
        if similarity > 0:
            neighbors.append((user_id, similarity))
    neighbors.sort(key=lambda neighbor: (-neighbor[1], neighbor[0]))
    return neighbors[:k]


def predict_ratings(
    target: Profile,
    users: UserRatings,
    neighbors: Iterable[Neighbor],
    min_neighbors: int = 1,
) -> dict[int, float]:
    """Predict unseen movies: target mean + sum(s * deviation) / sum(s).

    Deviations use each neighbor's mean over all their ratings. Only positive
    neighbors who rated a candidate contribute; unsupported movies are omitted.
    Repeated user IDs contribute once, using their first positive similarity.
    """
    if min_neighbors < 1:
        raise ValueError("min_neighbors must be positive")
    if not target:
        return {}
    target_mean = sum(target.values()) / len(target)
    weighted_deviations: dict[int, float] = {}
    similarity_sums: dict[int, float] = {}
    counts: dict[int, int] = {}
    seen_neighbors: set[int] = set()
    for user_id, similarity in neighbors:
        if similarity <= 0 or user_id in seen_neighbors:
            continue
        seen_neighbors.add(user_id)
        profile = users[user_id]
        if not profile:
            continue
        neighbor_mean = sum(profile.values()) / len(profile)
        for movie_id, rating in profile.items():
            if movie_id in target:
                continue
            weighted_deviations[movie_id] = (
                weighted_deviations.get(movie_id, 0.0)
                + similarity * (rating - neighbor_mean)
            )
            similarity_sums[movie_id] = similarity_sums.get(movie_id, 0.0) + similarity
            counts[movie_id] = counts.get(movie_id, 0) + 1
    predictions = {}
    for movie_id, deviation in weighted_deviations.items():
        if counts[movie_id] >= min_neighbors:
            prediction = target_mean + deviation / similarity_sums[movie_id]
            predictions[movie_id] = max(0.5, min(5.0, prediction))
    return predictions


def popular_recommendations(
    users: UserRatings,
    limit: int = 10,
    min_rating_count: int = 20,
    exclude_movies: Iterable[int] = (),
    allowed_movies: Iterable[int] | None = None,
) -> list[Recommendation]:
    """Rank by average, then rating count, then movie ID; threshold is inclusive."""
    if limit < 0 or min_rating_count < 1:
        raise ValueError("limit must be nonnegative and min_rating_count positive")
    excluded = set(exclude_movies)
    allowed = None if allowed_movies is None else set(allowed_movies)
    totals: dict[int, float] = {}
    counts: dict[int, int] = {}
    for profile in users.values():
        for movie_id, rating in profile.items():
            if movie_id in excluded or (allowed is not None and movie_id not in allowed):
                continue
            totals[movie_id] = totals.get(movie_id, 0.0) + rating
            counts[movie_id] = counts.get(movie_id, 0) + 1
    scores = [
        (movie_id, total / counts[movie_id])
        for movie_id, total in totals.items()
        if counts[movie_id] >= min_rating_count
    ]
    scores.sort(key=lambda item: (-item[1], -counts[item[0]], item[0]))
    return scores[:limit]


def genre_recommendations(
    genre: str,
    movies: pd.DataFrame,
    users: UserRatings,
    limit: int = 10,
    min_rating_count: int = 20,
    exclude_movies: Iterable[int] = (),
) -> list[Recommendation]:
    """Match a whole MovieLens genre token, ignoring case; unknown genres yield []."""
    requested = genre.strip().casefold()
    allowed = []
    for row in movies.itertuples(index=False):
        if requested in {token.casefold() for token in row.genres.split("|")}:
            allowed.append(int(row.movie_id))
    return popular_recommendations(users, limit, min_rating_count, exclude_movies, allowed)


def recommend(
    target: Profile,
    users: UserRatings,
    limit: int = 10,
    k: int = 15,
    min_overlap: int = 2,
    min_neighbors: int = 1,
    min_rating_count: int = 20,
    exclude_user_id: int | None = None,
) -> list[Recommendation]:
    """Return (movie_id, score): CF predictions, or popularity if none are usable.

    Fallback scores are historical averages, not personalized predictions.
    A short personalized list is returned as-is rather than mixing score types.
    """
    if limit < 0 or min_rating_count < 1:
        raise ValueError("limit must be nonnegative and min_rating_count positive")
    neighbors = nearest_neighbors(target, users, k, min_overlap, exclude_user_id)
    predictions = predict_ratings(target, users, neighbors, min_neighbors)
    if not predictions:
        return popular_recommendations(users, limit, min_rating_count, target)
    return sorted(predictions.items(), key=lambda item: (-item[1], item[0]))[:limit]


def combine_profiles(profiles: Iterable[Profile]) -> dict[int, float]:
    """Average only supplied ratings; missing ratings are not votes of zero."""
    totals: dict[int, float] = {}
    counts: dict[int, int] = {}
    for profile in profiles:
        for movie_id, rating in profile.items():
            totals[movie_id] = totals.get(movie_id, 0.0) + rating
            counts[movie_id] = counts.get(movie_id, 0) + 1
    return {movie_id: total / counts[movie_id] for movie_id, total in totals.items()}
