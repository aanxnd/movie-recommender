import pandas as pd
import pytest
from app import recommender

from app.recommender import (
    build_user_ratings,
    combine_profiles,
    genre_recommendations,
    nearest_neighbors,
    pearson_similarity,
    popular_recommendations,
    predict_ratings,
    recommend,
)


@pytest.fixture(autouse=True)
def unshrunk_control(monkeypatch):
    """Isolate core CF controls; accepted defaults have separate model tests."""
    monkeypatch.setattr(recommender, "PEARSON_SHRINKAGE", 0.)
    monkeypatch.setattr(recommender, "PREDICTION_SHRINKAGE", 0.)


def test_sparse_conversion_matches_loader_columns():
    frame = pd.DataFrame(
        [(1, 10, 4.5), (1, 20, 2.0), (2, 20, 3.0)],
        columns=["user_id", "movie_id", "rating"],
    )
    assert build_user_ratings(frame) == {1: {10: 4.5, 20: 2.0}, 2: {20: 3.0}}


def test_pearson_uses_only_overlap_and_handles_opposite_users():
    first = {1: 1.0, 2: 2.0, 3: 3.0, 99: 5.0}
    assert pearson_similarity(first, {1: 2.0, 2: 3.0, 3: 4.0, 98: 0.5}) == pytest.approx(1)
    assert pearson_similarity(first, {1: 5.0, 2: 4.0, 3: 3.0}) == pytest.approx(-1)
    assert pearson_similarity({1: 1, 2: 2, 3: 3}, {1: 3, 2: 1, 3: 3}) == pytest.approx(0)


@pytest.mark.parametrize("second", [{}, {9: 3}, {1: 5}, {1: 3, 2: 3}])
def test_undefined_pearson_returns_zero(second):
    assert pearson_similarity({1: 1, 2: 5}, second) == 0


def test_overlap_threshold_and_constant_target():
    assert pearson_similarity({1: 1, 2: 5}, {1: 2, 2: 4}, min_overlap=3) == 0
    assert pearson_similarity({1: 3, 2: 3}, {1: 1, 2: 5}) == 0


def test_constant_fractional_group_profile_has_zero_similarity():
    profiles = [dict.fromkeys(range(1, 26), rating) for rating in (0.5, 0.5, 1.0)]
    combined = combine_profiles(profiles)
    assert combined == dict.fromkeys(range(1, 26), 2 / 3)
    varying = {movie: float(1 + movie % 5) for movie in combined}
    assert pearson_similarity(combined, combined) == 0.0
    assert pearson_similarity(combined, varying) == 0.0
    assert pearson_similarity(varying, combined) == 0.0


def test_small_real_variation_is_not_treated_as_zero_variance():
    profile = {1: 3.0, 2: 3.0 + 1e-8, 3: 3.0 - 1e-8}
    assert pearson_similarity(profile, profile) == pytest.approx(1)


def test_neighbor_ordering_filters_nonpositive_and_excludes_self():
    target = {1: 1, 2: 2, 3: 3}
    users = {
        1: target,
        2: {1: 1, 2: 3, 3: 2},  # Pearson = 0.5
        3: {1: 2, 2: 3, 3: 4},  # Pearson = 1
        4: {1: 3, 2: 2, 3: 1},
        5: {1: 3, 2: 3, 3: 3},
        6: {9: 4},
    }
    neighbors = nearest_neighbors(target, users, k=10, exclude_user_id=1)
    assert [user_id for user_id, _ in neighbors] == [3, 2]
    assert [score for _, score in neighbors] == pytest.approx([1, 0.5])
    assert nearest_neighbors(target, users, k=1, exclude_user_id=1) == [neighbors[0]]


def test_equal_similarity_neighbors_use_user_id_order():
    target = {1: 1, 2: 5}
    users = {9: {1: 2, 2: 4}, 2: {1: 2, 2: 4}, 5: {1: 2, 2: 4}}
    assert nearest_neighbors(target, users, k=2) == [(2, 1.0), (5, 1.0)]


def test_mean_centered_weighted_prediction_and_support_threshold():
    target = {1: 2, 2: 4}  # mean 3
    users = {
        1: {1: 1, 2: 3, 3: 5},  # mean 3, movie 3 deviation +2
        2: {1: 1, 2: 3, 3: 2, 4: 4},  # mean 2.5; deviations -0.5 and +1.5
        3: {3: 0.5},
    }
    predictions = predict_ratings(target, users, [(1, 1), (2, 0.5), (3, -1)])
    assert predictions == pytest.approx({3: 3 + (2 - 0.25) / 1.5, 4: 4.5})
    assert predict_ratings(target, users, [(1, 1), (2, 0.5)], min_neighbors=2) == pytest.approx(
        {3: 3 + (2 - 0.25) / 1.5}
    )
    assert predict_ratings(target, users, [(1, 1)], min_neighbors=2) == {}


def test_duplicate_neighbors_do_not_change_weights_or_support():
    target = {1: 2, 2: 4}
    users = {1: {1: 1, 2: 3, 3: 5}, 2: {1: 1, 2: 3, 3: 2, 4: 4}}
    neighbors = [(1, 1), (1, 0.75), (2, 0.5)]
    assert predict_ratings(target, users, neighbors) == pytest.approx(
        {3: 3 + (2 - 0.25) / 1.5, 4: 4.5}
    )
    assert predict_ratings(target, users, [(1, 1), (1, 1)], min_neighbors=2) == {}


@pytest.mark.parametrize(
    "target, neighbor, expected",
    [({1: 4, 2: 5}, {1: 1, 2: 2, 3: 5}, 5),
     ({1: 0.5, 2: 1}, {1: 4, 2: 5, 3: 0.5}, 0.5)],
)
def test_predictions_clipped_to_movielens_range(target, neighbor, expected):
    assert predict_ratings(target, {1: neighbor}, [(1, 1)]) == {3: expected}


def test_personalized_ranking_limit_and_exclusion():
    target = {1: 1, 2: 5}
    users = {1: {1: 1, 2: 5, 3: 5, 4: 3, 5: 5}}
    # Neighbor mean = 3.8; target mean = 3. Predictions: 4.2, 2.2, 4.2.
    results = recommend(target, users, limit=3)
    assert [movie for movie, _ in results] == [3, 5, 4]
    assert [score for _, score in results] == pytest.approx([4.2, 4.2, 2.2])
    assert recommend(target, users, limit=1) == results[:1]
    assert recommend(target, users, limit=0) == []


def test_popularity_count_threshold_average_and_tie_order():
    users = {1: {1: 5, 2: 4, 3: 3, 4: 4}, 2: {2: 4, 3: 5, 4: 4}, 3: {3: 4}}
    assert popular_recommendations(users, min_rating_count=2) == [(3, 4), (2, 4), (4, 4)]
    assert popular_recommendations(users, min_rating_count=3) == [(3, 4)]
    assert popular_recommendations(users, min_rating_count=4) == []
    assert popular_recommendations(users, limit=1, min_rating_count=2, exclude_movies=[3]) == [(2, 4)]


@pytest.mark.parametrize("target, expected", [
    ({}, [(2, 5), (3, 4), (1, 1)]),
    ({1: 5}, [(2, 5), (3, 4)]),
    ({1: 3, 2: 3}, [(3, 4)]),
    ({90: 1, 91: 5}, [(2, 5), (3, 4), (1, 1)]),
])
def test_cold_start_and_unusable_neighbors_fall_back_excluding_seen(target, expected):
    users = {1: {1: 1, 2: 5, 3: 4}, 2: {1: 1, 2: 5, 3: 4}}
    assert recommend(target, users, min_rating_count=2) == expected


def test_no_supported_candidates_uses_fallback():
    users = {1: {1: 1, 2: 5}, 2: {3: 4}, 3: {3: 4}}
    assert recommend({1: 1, 2: 5}, users, min_rating_count=2) == [(3, 4)]
    assert recommend({}, {}, min_rating_count=2) == []


def test_all_negative_neighbors_use_popularity_fallback():
    users = {1: {1: 5, 2: 1, 3: 4}, 2: {1: 4, 2: 2, 3: 5}}
    assert recommend({1: 1, 2: 5}, users, min_rating_count=2) == [(3, 4.5)]


def test_support_threshold_failure_uses_popularity_fallback():
    users = {1: {1: 1, 2: 5, 3: 4}, 2: {3: 2}}
    # Only user 1 is a neighbor; both historical users count for popularity.
    assert recommend({1: 1, 2: 5}, users, min_neighbors=2, min_rating_count=2) == [(3, 3)]


def test_partial_personalized_output_is_not_padded_with_popularity():
    users = {1: {1: 1, 2: 5, 3: 3}, 2: {4: 5}, 3: {4: 5}}
    assert recommend({1: 1, 2: 5}, users, limit=5, min_rating_count=2) == [(3, 3)]


def test_genres_match_whole_tokens_and_use_popularity_threshold():
    movies = pd.DataFrame(
        [(1, "A", "Action|Sci-Fi"), (2, "B", "Drama|Sci-Fi"), (3, "C", "Action")],
        columns=["movie_id", "title", "genres"],
    )
    users = {1: {1: 4, 2: 3, 3: 5}, 2: {1: 4, 2: 4}}
    assert genre_recommendations(" sci-fi ", movies, users, min_rating_count=2) == [(1, 4), (2, 3.5)]
    assert genre_recommendations("Action", movies, users, min_rating_count=2) == [(1, 4)]
    assert genre_recommendations("Sci", movies, users, min_rating_count=2) == []
    assert genre_recommendations("Unknown", movies, users, min_rating_count=2) == []


def test_group_preserves_partial_preferences_and_excludes_union_of_seen_movies():
    combined = combine_profiles([{1: 1, 2: 5}, {2: 3, 3: 4}, {}])
    assert combined == {1: 1, 2: 4, 3: 4}
    users = {1: {1: 1, 2: 4, 3: 4, 4: 5}}
    results = recommend(combined, users)
    assert [movie for movie, _ in results] == [4]
    assert results[0][1] == pytest.approx(4.5)
    assert combine_profiles([]) == {}
    assert recommend(combine_profiles([{}, {}]), users, min_rating_count=1) == [(4, 5), (2, 4), (3, 4), (1, 1)]


@pytest.mark.parametrize("call", [
    lambda: pearson_similarity({}, {}, min_overlap=1),
    lambda: nearest_neighbors({}, {}, k=0),
    lambda: predict_ratings({}, {}, [], min_neighbors=0),
    lambda: recommend({}, {}, limit=-1),
    lambda: popular_recommendations({}, min_rating_count=0),
])
def test_invalid_algorithm_settings(call):
    with pytest.raises(ValueError):
        call()
