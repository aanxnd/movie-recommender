import pytest
from app import recommender

from app.recommender import (
    Prediction, available_decades, genre_adjusted_score, genre_preferences,
    movie_ids_for_decade, predict_ratings_with_confidence, recommend_details,
    release_year, popular_recommendations, confidence_ranking_score, recommend,
)


@pytest.fixture(autouse=True)
def unshrunk_control(monkeypatch):
    """Keep genre/confidence/ranking controls isolated from deviation shrinkage."""
    monkeypatch.setattr(recommender, "PEARSON_SHRINKAGE", 0.)
    monkeypatch.setattr(recommender, "PREDICTION_SHRINKAGE", 0.)


@pytest.mark.parametrize("title, expected", [
    ("Interstellar (2014)", 2014),
    ("Film (alternate title) (1999)  ", 1999),
    ("2001: A Space Odyssey (1968)", 1968),
    ("Film (2014) extra", None), ("Film 2014", None),
    ("Film (????)", None), ("Film (0999)", None), ("No year", None),
])
def test_release_year_is_a_valid_trailing_year(title, expected):
    assert release_year(title) == expected


def test_decades_are_sorted_unique_and_filter_boundaries_without_losing_unknown_years_in_all():
    years = {1: 1999, 2: 2000, 3: 2009, 4: 2010, 5: None}
    assert available_decades(years) == [1990, 2000, 2010]
    assert available_decades({1: None}) == []
    assert movie_ids_for_decade(years, None) is None
    assert movie_ids_for_decade(years, 2000) == {2, 3}
    assert movie_ids_for_decade(years, 1980) == set()
    users = {1: dict.fromkeys(years, 4)}
    assert len(popular_recommendations(users, min_rating_count=1)) == 5
    assert popular_recommendations(users, min_rating_count=1,
                                  allowed_movies=movie_ids_for_decade(years, 2000)) == [(2, 4), (3, 4)]


@pytest.mark.parametrize("decade", [1991, 1790, 2100, True, "2000"])
def test_invalid_engine_decades(decade):
    with pytest.raises(ValueError):
        movie_ids_for_decade({}, decade)


def test_decade_filter_precedes_personalized_limit_and_excludes_seen():
    target = {1: 1, 2: 5}
    users = {1: {1: 1, 2: 5, 3: 5, 4: 3, 5: 4}}
    years = {1: 2000, 2: 2001, 3: 1990, 4: 2009, 5: None}
    results = recommend_details(target, users, limit=1,
                                allowed_movies=movie_ids_for_decade(years, 2000))
    assert [row.movie_id for row in results] == [4]
    assert results[0].method == "collaborative_filtering"
    assert results[0].confidence == pytest.approx(0.4 / 3.4)
    assert [row.movie_id for row in recommend_details(target, users, limit=1)] == [3]


def test_filtered_cold_start_and_no_eligible_candidates_are_honest():
    users = {1: {1: 1, 2: 5, 3: 4}, 2: {1: 1, 2: 5, 3: 4}}
    years = {1: 2000, 2: 1999, 3: 2009}
    allowed = movie_ids_for_decade(years, 2000)
    for target in ({}, {1: 5}):
        results = recommend_details(target, users, min_rating_count=2, allowed_movies=allowed)
        assert [row.movie_id for row in results] == ([3, 1] if not target else [3])
        assert all(row.confidence is None and row.method == "popularity_fallback" for row in results)
    assert recommend_details({}, users, min_rating_count=1, allowed_movies=set()) == []
    assert recommend_details({1: 1, 2: 5}, users, allowed_movies=set()) == []


def test_popularity_can_fill_a_filtered_decade_with_no_cf_candidates():
    users = {1: {1: 1, 2: 5, 3: 4}, 2: {4: 5}, 3: {4: 3}}
    results = recommend_details({1: 1, 2: 5}, users, min_rating_count=2, allowed_movies={4})
    assert [(row.movie_id, row.score, row.confidence, row.method) for row in results] == [
        (4, 4, None, "popularity_fallback"),
    ]


def test_genre_preferences_use_deviations_and_shrink_sparse_evidence():
    genres = {1: ["Sci-Fi"], 2: ["Sci-Fi"], 3: ["Drama"], 4: ["Drama"]}
    assert genre_preferences({1: 5, 2: 5, 3: 1, 4: 1}, genres) == {"Sci-Fi": 0.8, "Drama": -0.8}
    assert genre_preferences({1: 5, 3: 1}, genres) == {"Sci-Fi": 0.5, "Drama": -0.5}
    assert genre_preferences({1: 5, 2: 5}, genres) == {"Sci-Fi": 0}
    assert genre_preferences({}, genres) == {}
    assert genre_preferences({1: 5, 3: 1}, {1: ["(no genres listed)"]}) == {}


@pytest.mark.parametrize("genres, expected", [
    (["Sci-Fi"], 3.08), (["Drama"], 2.92), (["Adventure"], 3),
    (["Sci-Fi", "Drama"], 3), (["Sci-Fi", "Adventure"], 3.04),
    (["Sci-Fi", "Sci-Fi"], 3.08), ([], 3), (["(no genres listed)"], 3),
])
def test_genre_adjustment_handles_preferred_disliked_unseen_and_multiple(genres, expected):
    assert genre_adjusted_score(Prediction(3, 0.5), genres, {"Sci-Fi": 0.8, "Drama": -0.8}) == pytest.approx(expected)


def test_genre_adjustment_is_bounded_clipped_and_damped_by_evidence():
    preferences = {"Sci-Fi": 4.5, "Drama": -4.5}
    assert genre_adjusted_score(Prediction(3, 1), ["Sci-Fi"], preferences) == 3.35
    assert genre_adjusted_score(Prediction(3, 1), ["Drama"], preferences) == 2.65
    assert genre_adjusted_score(Prediction(5, 1), ["Sci-Fi"], preferences) == 5
    assert genre_adjusted_score(Prediction(0.5, 1), ["Drama"], preferences) == 0.5
    weak = genre_adjusted_score(Prediction(3, 0.1), ["Sci-Fi"], preferences)
    strong = genre_adjusted_score(Prediction(4.5, 1), ["Drama"], preferences)
    assert weak == pytest.approx(3.09)
    assert strong > weak


def test_genres_modestly_rerank_equal_cf_candidates_without_changing_confidence_or_seen_exclusion():
    target = {1: 5, 2: 5, 3: 1, 4: 1}
    users = {1: {**target, 5: 3, 6: 3, 7: 3}}
    genres = {1: ["Sci-Fi"], 2: ["Sci-Fi"], 3: ["Drama"], 4: ["Drama"],
              5: ["Drama"], 6: ["Adventure"], 7: ["Sci-Fi"]}
    results = recommend_details(target, users, genres=genres)
    assert [row.movie_id for row in results] == [7, 6, 5]
    confidence = 0.8 / 3.8
    assert [row.score for row in results] == pytest.approx([3 + .2 * confidence * .8, 3, 3 - .2 * confidence * .8])
    assert [row.ranking_score for row in results] == pytest.approx([
        3 + .2 * confidence ** 2 * .8, 3, 3 - .2 * confidence ** 2 * .8,
    ])
    assert all(row.confidence == pytest.approx(confidence) for row in results)
    assert [row.movie_id for row in recommend_details(target, users, genres=genres, genre_weight=0)] == [5, 6, 7]


def test_confidence_more_stronger_and_more_overlap_support_increases_evidence():
    target = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
    users = {1: {1: 1, 2: 2, 9: 5}, 2: {**target, 9: 5}}
    weak = predict_ratings_with_confidence(target, users, [(1, .2)])[9].confidence
    stronger = predict_ratings_with_confidence(target, users, [(1, 1)])[9].confidence
    overlap = predict_ratings_with_confidence(target, users, [(2, 1)])[9].confidence
    more = predict_ratings_with_confidence(target, users, [(1, 1), (2, 1)])[9].confidence
    assert weak == pytest.approx(.08 / 3.08)
    assert stronger == pytest.approx(.4 / 3.4)
    assert overlap == pytest.approx(1 / 4)
    assert more == pytest.approx(1.4 / 4.4)
    assert 0 < weak < stronger < overlap < more < 1
    assert predict_ratings_with_confidence(target, users, [(1, 1), (1, 1)])[9].confidence == stronger
    assert predict_ratings_with_confidence(target, users, [(1, 1)], min_neighbors=2) == {}


def test_high_predictions_do_not_imply_high_confidence():
    target = {1: 4, 2: 5}
    predictions = predict_ratings_with_confidence(target, {1: {1: 1, 2: 2, 3: 5, 4: 1}}, [(1, 1)])
    assert predictions[3].score == 5
    assert predictions[3].confidence == predictions[4].confidence == pytest.approx(.4 / 3.4)
    assert predictions[4].score < predictions[3].score


def test_fallback_ignores_genre_preferences():
    results = recommend_details({1: 5}, {1: {1: 5, 2: 3}}, genres={1: ["Sci-Fi"], 2: ["Sci-Fi"]}, min_rating_count=1)
    assert [(row.movie_id, row.score, row.confidence, row.method) for row in results] == [(2, 3, None, "popularity_fallback")]


@pytest.mark.parametrize("weight", [-.1, 1.1, float('nan')])
def test_invalid_genre_weights(weight):
    with pytest.raises(ValueError):
        recommend_details({}, {}, genre_weight=weight)


@pytest.mark.parametrize("better, worse", [
    ((4.4, .65), (5, .12)),
    ((4.3, .60), (5, .12)),
    ((4.4, .60), (4.0, .60)),
    ((4.4, .65), (4.4, .12)),
    ((4.4, .65), (2, .90)),
])
def test_confidence_ranking_balances_preference_and_evidence(better, worse):
    assert confidence_ranking_score(*better, 3.5) > confidence_ranking_score(*worse, 3.5)


def test_ranking_shrinkage_has_understandable_values_and_endpoints():
    assert confidence_ranking_score(5, .12, 3.5) == pytest.approx(3.68)
    assert confidence_ranking_score(4.4, .65, 3.5) == pytest.approx(4.085)
    assert confidence_ranking_score(2, .90, 3.5) == pytest.approx(2.15)
    assert confidence_ranking_score(5, 0, 3.5) == 3.5
    assert confidence_ranking_score(4.4, 1, 3.5) == 4.4


def test_details_sort_by_ranking_not_display_score_and_use_rating_weighted_baseline(monkeypatch):
    # Historical mean = (1 + 5 + 4 + 4) / 4 = 3.5, not mean(user means).
    users = {1: {1: 1, 2: 5, 8: 4}, 2: {9: 4}}
    predictions = {10: Prediction(5, .12, 8), 11: Prediction(4.4, .65, 4.4),
                   12: Prediction(2, .90, 2), 13: Prediction(4.4, .65, 4.4)}
    monkeypatch.setattr("app.recommender.predict_ratings_with_confidence", lambda *args: predictions)
    first = recommend_details({1: 1, 2: 5}, users)
    assert [row.movie_id for row in first] == [11, 13, 10, 12]
    assert [row.score for row in first] == [4.4, 4.4, 5, 2]
    assert [row.confidence for row in first] == [.65, .65, .12, .90]
    assert [row.ranking_score for row in first] == pytest.approx([4.085, 4.085, 3.68, 2.15])
    # Reversing dictionary insertion order must not change ties or the baseline.
    predictions = dict(reversed(list(predictions.items())))
    assert recommend_details({1: 1, 2: 5}, dict(reversed(list(users.items())))) == first


def test_raw_cf_breaks_saturation_ties_without_changing_display_or_legacy_order():
    target = {1: 4, 2: 5}
    users = {1: {1: 1, 2: 2, 3: 4, 4: 5}}
    predictions = predict_ratings_with_confidence(target, users, [(1, 1)])
    assert predictions[3].raw_score == 5.5
    assert predictions[4].raw_score == 6.5
    assert predictions[3].score == predictions[4].score == 5
    results = recommend_details(target, users)
    assert [row.movie_id for row in results] == [4, 3]
    assert results[0].ranking_score == results[1].ranking_score
    assert all(.5 <= row.score <= 5 for row in results)
    assert recommend(target, users) == [(3, 5), (4, 5)]


def test_confidence_ranking_keeps_fallback_average_count_id_order_and_null_evidence():
    users = {1: {1: 4, 2: 4, 3: 4, 4: 5}, 2: {2: 4, 3: 4}}
    for target in ({}, {4: 5}):
        results = recommend_details(target, users, min_rating_count=1)
        assert [(row.movie_id, row.score) for row in results] == popular_recommendations(
            users, min_rating_count=1, exclude_movies=target,
        )
        assert all(row.confidence is None and row.ranking_score is None for row in results)
