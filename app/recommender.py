"""Readable user-user collaborative filtering over validated MovieLens data."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import sqrt
import re

import pandas as pd


Profile = Mapping[int, float]
UserRatings = Mapping[int, Profile]
Neighbor = tuple[int, float]
Recommendation = tuple[int, float]
GENRE_WEIGHT = 0.20
GENRE_PRIOR_COUNT = 3
MAX_GENRE_ADJUSTMENT = 0.35
CONFIDENCE_OVERLAP_TARGET = 5
CONFIDENCE_SUPPORT_SCALE = 3


@dataclass(frozen=True)
class Prediction:
    score: float
    confidence: float
    raw_score: float | None = None


@dataclass(frozen=True)
class RecommendationResult:
    movie_id: int
    score: float
    confidence: float | None
    method: str
    ranking_score: float | None = None


def confidence_ranking_score(score: float, confidence: float, baseline: float) -> float:
    """Shrink a bounded final prediction toward the historical rating mean."""
    return baseline + confidence * (score - baseline)


def release_year(title: str) -> int | None:
    """Use only a trailing MovieLens (YYYY), not numbers inside a title."""
    match = re.search(r"\((\d{4})\)\s*$", title)
    if match and 1800 <= int(match[1]) <= 2099:
        return int(match[1])
    return None


def available_decades(years: Mapping[int, int | None]) -> list[int]:
    return sorted({year // 10 * 10 for year in years.values() if year is not None})


def movie_ids_for_decade(years: Mapping[int, int | None], decade: int | None) -> set[int] | None:
    if decade is None:
        return None
    if isinstance(decade, bool) or not isinstance(decade, int) or not 1800 <= decade <= 2090 or decade % 10:
        raise ValueError("decade must be a multiple of 10 between 1800 and 2090")
    return {movie for movie, year in years.items() if year is not None and decade <= year < decade + 10}


def genre_preferences(target: Profile, genres: Mapping[int, list[str]]) -> dict[str, float]:
    if not target:
        return {}
    mean = sum(target.values()) / len(target)
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for movie, rating in target.items():
        for genre in set(genres.get(movie, [])) - {"(no genres listed)"}:
            totals[genre] = totals.get(genre, 0.0) + rating - mean
            counts[genre] = counts.get(genre, 0) + 1
    return {genre: total / (counts[genre] + GENRE_PRIOR_COUNT) for genre, total in totals.items()}


def genre_adjusted_score(
    prediction: Prediction, genres: list[str], preferences: Mapping[str, float],
    genre_weight: float = GENRE_WEIGHT,
) -> float:
    known_genres = set(genres) - {"(no genres listed)"}
    preference = sum(preferences.get(genre, 0.0) for genre in known_genres) / len(known_genres) if known_genres else 0.0
    adjustment = genre_weight * prediction.confidence * preference
    adjustment = max(-MAX_GENRE_ADJUSTMENT, min(MAX_GENRE_ADJUSTMENT, adjustment))
    return max(0.5, min(5.0, prediction.score + adjustment))


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
    """Preserve the original score-only interface for Python callers."""
    return {movie: prediction.score for movie, prediction in predict_ratings_with_confidence(
        target, users, neighbors, min_neighbors,
    ).items()}


def predict_ratings_with_confidence(
    target: Profile,
    users: UserRatings,
    neighbors: Iterable[Neighbor],
    min_neighbors: int = 1,
    allowed_movies: Iterable[int] | None = None,
) -> dict[int, Prediction]:
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
    evidence_sums: dict[int, float] = {}
    allowed = None if allowed_movies is None else set(allowed_movies)
    seen_neighbors: set[int] = set()
    for user_id, similarity in neighbors:
        if similarity <= 0 or user_id in seen_neighbors:
            continue
        seen_neighbors.add(user_id)
        profile = users[user_id]
        if not profile:
            continue
        neighbor_mean = sum(profile.values()) / len(profile)
        overlap = len(target.keys() & profile.keys())
        evidence = min(1.0, similarity) * min(overlap / CONFIDENCE_OVERLAP_TARGET, 1.0)
        for movie_id, rating in profile.items():
            if movie_id in target or (allowed is not None and movie_id not in allowed):
                continue
            weighted_deviations[movie_id] = (
                weighted_deviations.get(movie_id, 0.0)
                + similarity * (rating - neighbor_mean)
            )
            similarity_sums[movie_id] = similarity_sums.get(movie_id, 0.0) + similarity
            counts[movie_id] = counts.get(movie_id, 0) + 1
            evidence_sums[movie_id] = evidence_sums.get(movie_id, 0.0) + evidence
    predictions = {}
    for movie_id, deviation in weighted_deviations.items():
        if counts[movie_id] >= min_neighbors:
            prediction = target_mean + deviation / similarity_sums[movie_id]
            evidence = evidence_sums[movie_id]
            confidence = evidence / (evidence + CONFIDENCE_SUPPORT_SCALE)
            predictions[movie_id] = Prediction(max(0.5, min(5.0, prediction)), confidence, prediction)
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
    allowed_movies: Iterable[int] | None = None,
) -> list[Recommendation]:
    """Match a whole MovieLens genre token, ignoring case; unknown genres yield []."""
    requested = genre.strip().casefold()
    allowed = []
    candidates = None if allowed_movies is None else set(allowed_movies)
    for row in movies.itertuples(index=False):
        if requested in {token.casefold() for token in row.genres.split("|")} and (candidates is None or int(row.movie_id) in candidates):
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
    """Preserve the original tuple interface and unadjusted Python behavior."""
    return [(row.movie_id, row.score) for row in recommend_details(
        target, users, limit, k, min_overlap, min_neighbors, min_rating_count, exclude_user_id,
        rank_by_confidence=False,
    )]


def recommend_details(
    target: Profile,
    users: UserRatings,
    limit: int = 10,
    k: int = 15,
    min_overlap: int = 2,
    min_neighbors: int = 1,
    min_rating_count: int = 20,
    exclude_user_id: int | None = None,
    *,
    genres: Mapping[int, list[str]] | None = None,
    allowed_movies: Iterable[int] | None = None,
    genre_weight: float = GENRE_WEIGHT,
    rank_by_confidence: bool = True,
) -> list[RecommendationResult]:
    """Rank CF predictions with genre adjustment, or return labeled popularity.

    Fallback scores are historical averages, not personalized predictions.
    A short personalized list is returned as-is rather than mixing score types.
    """
    if limit < 0 or min_rating_count < 1:
        raise ValueError("limit must be nonnegative and min_rating_count positive")
    if not 0 <= genre_weight <= 1:
        raise ValueError("genre_weight must be between 0 and 1")
    allowed = None if allowed_movies is None else set(allowed_movies)
    neighbors = nearest_neighbors(target, users, k, min_overlap, exclude_user_id)
    predictions = predict_ratings_with_confidence(target, users, neighbors, min_neighbors, allowed)
    if not predictions:
        return [RecommendationResult(movie, score, None, "popularity_fallback") for movie, score in
                popular_recommendations(users, limit, min_rating_count, target, allowed)]
    preferences = genre_preferences(target, genres or {})
    # CF candidates imply nonempty historical ratings. Use every historical
    # rating equally; the baseline is independent of the target and decade.
    baseline = sum(sum(profile.values()) for profile in users.values()) / sum(len(profile) for profile in users.values())
    results = []
    for movie, prediction in predictions.items():
        score = genre_adjusted_score(prediction, (genres or {}).get(movie, []), preferences, genre_weight)
        results.append(RecommendationResult(
            movie, score, prediction.confidence, "collaborative_filtering",
            confidence_ranking_score(score, prediction.confidence, baseline),
        ))
    if not rank_by_confidence:
        return sorted(results, key=lambda row: (-row.score, row.movie_id))[:limit]
    # Raw extrapolations only resolve equal ranking AND displayed scores;
    # they cannot overcome the primary confidence shrinkage or genre signal.
    return sorted(results, key=lambda row: (
        -row.ranking_score, -row.score,
        -(predictions[row.movie_id].raw_score if predictions[row.movie_id].raw_score is not None else row.score),
        row.movie_id,
    ))[:limit]


def combine_profiles(profiles: Iterable[Profile]) -> dict[int, float]:
    """Average only supplied ratings; missing ratings are not votes of zero."""
    totals: dict[int, float] = {}
    counts: dict[int, int] = {}
    for profile in profiles:
        for movie_id, rating in profile.items():
            totals[movie_id] = totals.get(movie_id, 0.0) + rating
            counts[movie_id] = counts.get(movie_id, 0) + 1
    return {movie_id: total / counts[movie_id] for movie_id, total in totals.items()}
