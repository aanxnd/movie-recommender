from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import database
from app.main import create_app


@pytest.fixture
def api_paths(tmp_path: Path) -> tuple[Path, Path]:
    pd.DataFrame([
        (1, "First Film", "Action|Sci-Fi"),
        (2, "Second Film", "Drama"),
        (3, "Third Film", "Action"),
        (4, "Fourth Film", "Drama"),
        (5, "Fifth Film", "Comedy"),
    ], columns=["movieId", "title", "genres"]).to_csv(tmp_path / "movies.csv", index=False)
    # Historical user 1 must remain a neighbor of application user 1.
    pd.DataFrame([
        (1, 1, 1), (1, 2, 5), (1, 3, 5), (1, 4, 3), (1, 5, 5),
        (2, 1, 5), (2, 2, 1), (2, 3, 4),
    ], columns=["userId", "movieId", "rating"]).to_csv(tmp_path / "ratings.csv", index=False)
    return tmp_path, tmp_path / "api.db"


@pytest.fixture
def client(api_paths):
    with TestClient(create_app(*api_paths)) as client:
        yield client


def new_user(client) -> int:
    response = client.post("/users")
    assert response.status_code == 201
    return response.json()["id"]


def rate(client, user_id, movie_id, rating):
    response = client.put(f"/users/{user_id}/ratings/{movie_id}", json={"rating": rating})
    assert response.status_code == 200
    return response.json()


def test_health_and_documented_endpoints(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/recommendations/group" in schema["paths"]
    assert "RatingRequest" in schema["components"]["schemas"]


def test_search_and_lookup(client):
    expected = {"movie_id": 1, "title": "First Film", "genres": ["Action", "Sci-Fi"]}
    response = client.get("/movies/search", params={"q": " FIRST "})
    assert response.status_code == 200
    assert response.json() == [expected]
    assert client.get("/movies/1").json() == expected
    assert len(client.get("/movies/search?q=film&limit=2").json()) == 2
    for query in ("", "   ", "absent", ".*"):
        assert client.get("/movies/search", params={"q": query}).json() == []
    assert client.get("/movies/999").status_code == 404


def test_users_ratings_updates_and_isolation(client):
    first, second = new_user(client), new_user(client)
    assert first != second
    assert client.get(f"/users/{first}").json() == {"id": first}
    assert client.get(f"/users/{first}/ratings").json() == []
    assert rate(client, first, 2, 5) == {"user_id": first, "movie_id": 2, "rating": 5}
    rate(client, first, 1, 0.5)
    rate(client, first, 2, 3.25)
    assert client.get(f"/users/{first}/ratings").json() == [
        {"user_id": first, "movie_id": 1, "rating": 0.5},
        {"user_id": first, "movie_id": 2, "rating": 3.25},
    ]
    assert client.get(f"/users/{second}/ratings").json() == []


@pytest.mark.parametrize("body", [
    {}, {"rating": 0}, {"rating": 5.01}, {"rating": True},
    {"rating": "4"}, {"rating": None}, {"rating": "NaN"},
])
def test_invalid_ratings_preserve_saved_value(client, body):
    user_id = new_user(client)
    rate(client, user_id, 1, 4)
    assert client.put(f"/users/{user_id}/ratings/1", json=body).status_code == 422
    assert client.get(f"/users/{user_id}/ratings").json()[0]["rating"] == 4


def test_missing_users_and_movies(client):
    for path in ("/users/999", "/users/999/ratings", "/users/999/recommendations"):
        assert client.get(path).status_code == 404
    assert client.put("/users/999/ratings/1", json={"rating": 4}).status_code == 404
    user_id = new_user(client)
    assert client.put(f"/users/{user_id}/ratings/999", json={"rating": 4}).status_code == 404
    assert client.get(f"/users/{user_id}/ratings").json() == []


@pytest.mark.parametrize("path", [
    "/movies/0", "/movies/9223372036854775808", "/users/-1", "/users/nope",
    "/movies/search?limit=0", "/movies/search?limit=101",
    "/recommendations/popular?min_rating_count=0", "/recommendations/popular?limit=nope",
    "/recommendations/genre/Action?limit=-1",
])
def test_invalid_parameters(client, path):
    assert client.get(path).status_code == 422


def test_popular_and_genre_recommendations(client):
    assert client.get("/recommendations/popular").json() == []
    response = client.get("/recommendations/popular?min_rating_count=2&limit=2")
    assert response.status_code == 200
    assert [(row["movie_id"], row["score"]) for row in response.json()] == [(3, 4.5), (1, 3)]
    assert response.json()[0]["title"] == "Third Film"
    assert response.json()[0]["genres"] == ["Action"]
    assert [row["movie_id"] for row in client.get(
        "/recommendations/genre/aCtIoN?min_rating_count=2",
    ).json()] == [3, 1]
    for genre in ("Unknown", "Sci", " "):
        assert client.get(f"/recommendations/genre/{genre}").json() == []


def test_personalized_scores_and_seen_exclusion(client):
    user_id = new_user(client)
    rate(client, user_id, 1, 1)
    rate(client, user_id, 2, 5)
    response = client.get(f"/users/{user_id}/recommendations")
    assert response.status_code == 200
    rows = response.json()
    # Genre deviations: Action -0.5, Drama +0.5; one neighbor with two shared movies.
    confidence = 0.4 / 3.4
    assert [row["movie_id"] for row in rows] == [5, 3, 4]
    assert [row["score"] for row in rows] == pytest.approx([4.2, 4.2 - .2 * confidence * .5, 2.2 + .2 * confidence * .5])
    assert all(row["confidence"] == pytest.approx(confidence) and row["method"] == "collaborative_filtering" for row in rows)
    assert client.get(f"/users/{user_id}/recommendations?limit=1").json() == rows[:1]


def test_cold_start_and_one_rating_fallback(client):
    user_id = new_user(client)
    path = f"/users/{user_id}/recommendations?min_rating_count=2"
    assert [row["movie_id"] for row in client.get(path).json()] == [3, 1, 2]
    rate(client, user_id, 3, 5)
    assert [row["movie_id"] for row in client.get(path).json()] == [1, 2]


def test_group_combines_saved_profiles_and_excludes_union(client):
    first, second = new_user(client), new_user(client)
    rate(client, first, 1, 1)
    rate(client, first, 2, 5)
    rate(client, second, 2, 3)
    rate(client, second, 3, 4)
    response = client.post("/recommendations/group", json={"user_ids": [first, second]})
    assert response.status_code == 200
    rows = response.json()
    assert [row["movie_id"] for row in rows] == [5, 4]
    # Combined mean 3, Drama preference (4 - 3) / (1 + 3); overlap is three.
    assert [row["score"] for row in rows] == pytest.approx([4.2, 2.2 + .2 * (.6 / 3.6) * .25])
    assert all(row["confidence"] == pytest.approx(.6 / 3.6) for row in rows)


def test_group_cold_start_and_missing_member(client):
    users = [new_user(client), new_user(client)]
    response = client.post("/recommendations/group?min_rating_count=2", json={"user_ids": users})
    assert [row["movie_id"] for row in response.json()] == [3, 1, 2]
    assert client.post("/recommendations/group", json={"user_ids": [users[0], 999]}).status_code == 404


@pytest.mark.parametrize("ids", [[], [1], [1, 1], [1, 0], [1, 2**63], [True, 2], ["1", 2]])
def test_invalid_groups(client, ids):
    assert client.post("/recommendations/group", json={"user_ids": ids}).status_code == 422


def test_database_persists_across_app_restarts(api_paths):
    with TestClient(create_app(*api_paths)) as first:
        user_id = new_user(first)
        rate(first, user_id, 1, 4.5)
    with TestClient(create_app(*api_paths)) as reopened:
        assert reopened.get(f"/users/{user_id}/ratings").json() == [
            {"user_id": user_id, "movie_id": 1, "rating": 4.5},
        ]


def test_each_fixture_starts_with_empty_application_database(client):
    assert client.get("/users/1").status_code == 404
    assert new_user(client) == 1


def test_database_error_is_sanitized_and_write_rolled_back(client, monkeypatch):
    original = database.create_user

    def failing_create(session):
        original(session)
        raise OperationalError("private SQL", {}, Exception("private details"))

    with monkeypatch.context() as patch:
        patch.setattr(database, "create_user", failing_create)
        response = client.post("/users")
    assert response.status_code == 500
    assert response.json() == {"detail": "Database operation failed"}
    assert client.get("/users/1").status_code == 404
    assert new_user(client) == 1


@pytest.mark.parametrize("write_kind", ["user", "rating"])
def test_commit_failure_returns_error_and_rolls_back(client, monkeypatch, write_kind):
    user_id = new_user(client)
    rate(client, user_id, 1, 4)
    engine = client.app.state.engine
    commit_attempts = []

    def failing_commit(connection):
        commit_attempts.append(connection)
        raise OperationalError("COMMIT", {}, Exception("private commit failure"))

    # Fail where SQLAlchemy would commit to SQLite, after the endpoint's writes.
    with monkeypatch.context() as patch:
        patch.setattr(engine.dialect, "do_commit", failing_commit)
        if write_kind == "user":
            response = client.post("/users")
        else:
            response = client.put(f"/users/{user_id}/ratings/1", json={"rating": 5})
    assert len(commit_attempts) == 1
    assert response.status_code == 500
    assert response.json() == {"detail": "Database operation failed"}
    assert engine.pool.checkedout() == 0
    assert client.get("/users/2").status_code == 404
    assert client.get(f"/users/{user_id}/ratings").json() == [
        {"user_id": user_id, "movie_id": 1, "rating": 4},
    ]
    assert new_user(client) == 2


@pytest.mark.parametrize("numeric_text", ["1e400", "NaN", "Infinity", "-Infinity"])
def test_nonfinite_numeric_rating_returns_422_without_persisting(client, numeric_text):
    user_id = new_user(client)
    rate(client, user_id, 1, 4)
    for movie_id in (1, 2):
        response = client.put(
            f"/users/{user_id}/ratings/{movie_id}",
            content='{"rating": ' + numeric_text + '}',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422
        details = response.json()["detail"]
        assert details[0]["loc"] == ["body", "rating"]
        assert details[0]["type"] == "finite_number"
        assert isinstance(details[0]["input"], str)
    assert client.get(f"/users/{user_id}/ratings").json() == [
        {"user_id": user_id, "movie_id": 1, "rating": 4},
    ]


@pytest.fixture
def dated_client(api_paths):
    movies = pd.read_csv(api_paths[0] / "movies.csv")
    movies["title"] = ["First Film (1999)", "Second Film (2000)", "Third Film (1990)",
                       "Fourth Film (2009)", "Fifth Film"]
    movies.loc[len(movies)] = [6, "Unrated Film (1901)", "Drama"]
    movies.to_csv(api_paths[0] / "movies.csv", index=False)
    with TestClient(create_app(*api_paths)) as client:
        yield client


def test_catalog_decades_are_derived_and_route_does_not_conflict_with_movie_lookup(dated_client):
    assert dated_client.get('/movies/decades').json() == [1900, 1990, 2000]
    assert dated_client.get('/movies/1').json()['title'] == 'First Film (1999)'


@pytest.mark.parametrize('decade', ['1991', '1790', '2100', 'nope', '2000.5', ''])
def test_decade_validation_on_all_recommendation_routes(dated_client, decade):
    user = new_user(dated_client)
    second = new_user(dated_client)
    for path in ['/recommendations/popular', '/recommendations/genre/Drama',
                 f'/users/{user}/recommendations']:
        assert dated_client.get(path, params={'decade': decade}).status_code == 422
    assert dated_client.post('/recommendations/group', params={'decade': decade},
                             json={'user_ids': [user, second]}).status_code == 422


def test_decade_constrains_popular_genre_personalized_and_fallback(dated_client):
    client = dated_client
    popular = client.get('/recommendations/popular?decade=2000&min_rating_count=1').json()
    assert [row['movie_id'] for row in popular] == [2, 4]
    assert all(row['confidence'] is None and row['method'] == 'popularity' for row in popular)
    assert [row['movie_id'] for row in client.get('/recommendations/genre/Drama?decade=2000&min_rating_count=1').json()] == [2, 4]
    user = new_user(client)
    fallback = client.get(f'/users/{user}/recommendations?decade=1990&min_rating_count=2').json()
    assert [row['movie_id'] for row in fallback] == [3, 1]
    assert all(row['confidence'] is None and row['method'] == 'popularity_fallback' for row in fallback)
    rate(client, user, 1, 1)
    rate(client, user, 2, 5)
    rows = client.get(f'/users/{user}/recommendations?decade=2000').json()
    assert [row['movie_id'] for row in rows] == [4]
    assert rows[0]['score'] == pytest.approx(2.2 + .2 * (.4 / 3.4) * .5)
    assert rows[0]['confidence'] == pytest.approx(.4 / 3.4)
    assert rows[0]['method'] == 'collaborative_filtering'
    # No-year movies remain eligible with the decade omitted.
    assert 5 in [row['movie_id'] for row in client.get(f'/users/{user}/recommendations').json()]
    for path in ['/recommendations/popular', '/recommendations/genre/Drama', f'/users/{user}/recommendations']:
        response = client.get(path, params={'decade': 1900, 'min_rating_count': 1})
        assert response.status_code == 200
        assert response.json() == []
        assert client.get(path, params={'decade': 2090}).json() == []


def test_group_decade_confidence_genres_and_union_exclusion(dated_client):
    client = dated_client
    first, second = new_user(client), new_user(client)
    cold = client.post('/recommendations/group?decade=1990&min_rating_count=2', json={'user_ids': [first, second]}).json()
    assert [row['movie_id'] for row in cold] == [3, 1]
    assert all(row['confidence'] is None and row['method'] == 'popularity_fallback' for row in cold)
    rate(client, first, 1, 1)
    rate(client, first, 2, 5)
    rate(client, second, 2, 3)
    rate(client, second, 3, 4)
    rows = client.post('/recommendations/group?decade=2000', json={'user_ids': [first, second]}).json()
    assert [row['movie_id'] for row in rows] == [4]
    assert rows[0]['genres'] == ['Drama']
    assert rows[0]['confidence'] == pytest.approx(.6 / 3.6)
    assert rows[0]['score'] == pytest.approx(2.2 + .2 * (.6 / 3.6) * .25)
    assert rows[0]['method'] == 'collaborative_filtering'
    assert client.post('/recommendations/group?decade=1900', json={'user_ids': [first, second]}).json() == []


@pytest.mark.parametrize("mode", ["personal", "group"])
def test_http_recommendations_rank_unequal_confidence_before_display_score(tmp_path, mode):
    pd.DataFrame([
        (movie, f"Film {movie}", "Drama") for movie in range(1, 5)
    ], columns=["movieId", "title", "genres"]).to_csv(tmp_path / "movies.csv", index=False)
    pd.DataFrame([
        (1, 1, 1), (1, 2, 2), (1, 3, 5), (1, 4, 2),
        (2, 1, 1), (2, 2, 2), (2, 4, 2),
    ], columns=["userId", "movieId", "rating"]).to_csv(tmp_path / "ratings.csv", index=False)
    with TestClient(create_app(tmp_path, tmp_path / "ranking.db")) as client:
        user = new_user(client)
        rate(client, user, 1, 4)
        rate(client, user, 2, 5)
        if mode == "personal":
            response = client.get(f"/users/{user}/recommendations")
        else:
            # An unrated member leaves the combined target profile unchanged.
            second = new_user(client)
            response = client.post("/recommendations/group", json={"user_ids": [user, second]})

    assert response.status_code == 200
    rows = response.json()
    # Both Pearson similarities are 1 with overlap 2; neighbor means are 5/2
    # and 5/3. Target mean is 9/2, and the shared Drama preference is zero.
    # Movie 3 has one contributor: raw CF 7 clips to 5, E=2/5, C=2/17.
    # Movie 4 has two: CF 9/2 + ((-1/2)+(1/3))/2 = 53/12,
    # E=4/5, C=4/19. Historical baseline is 15/7 across seven ratings.
    scores = [53 / 12, 5]
    confidences = [4 / 19, 2 / 17]
    baseline = 15 / 7
    ranking_scores = [baseline + confidence * (score - baseline)
                      for score, confidence in zip(scores, confidences)]
    assert scores[0] < scores[1] and confidences[0] > confidences[1]
    assert ranking_scores[0] > ranking_scores[1]
    assert [row["movie_id"] for row in rows] == [4, 3]
    assert [row["score"] for row in rows] == pytest.approx(scores)
    assert [row["confidence"] for row in rows] == pytest.approx(confidences)
    assert all(row["method"] == "collaborative_filtering" and "ranking_score" not in row for row in rows)
