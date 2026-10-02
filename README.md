# Movie Recommender

A learning-focused Python application being built incrementally from an educational movie recommender. The intended application will use FastAPI, SQLite, and an independently implemented user-user collaborative-filtering engine, with a small HTML/JavaScript frontend.

**Current status: Stage 2 (recommendation engine).** Data loading and the recommendation engine are implemented. Database, API, and website stages are still pending. LensKit is not a dependency.

## Setup

Use Python 3.11 or newer. From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/load_movielens.py
.\.venv\Scripts\python.exe -m pytest
```

On macOS/Linux, use `.venv/bin/python` in place of `.\.venv\Scripts\python.exe`.

The loader downloads MovieLens directly from GroupLens when CSV files are absent. Subsequent runs validate existing files without downloading. Use `--download` to replace them explicitly, or `--data-dir PATH` to choose a different directory. Downloads require internet access; tests do not.

If Python reports a certificate trust error, download the ZIP from the official GroupLens link using your browser, then import it with `python scripts/load_movielens.py --archive PATH_TO_ZIP`. Certificate verification remains enabled. This also supports offline imports.

## Data foundation

`app/data.py` exposes `load_movielens(data_dir)`, returning two pandas DataFrames:

- Movies: `movie_id`, `title`, `genres` (the original pipe-separated genre text).
- Historical ratings: `user_id`, `movie_id`, `rating`.

The loader validates required columns, nonempty data, missing values, positive integer IDs, unique movie IDs, unique user/movie rating pairs, rating bounds, and movie references. Extra source columns, such as timestamps, are omitted explicitly. MovieLens IDs are preserved.

Historical MovieLens users and ratings are reference data for the future engine. Application users and their submitted ratings will be stored separately in SQLite. Downloaded data, local databases, and the virtual environment are ignored by Git.

pandas handles CSV tables; NumPy supports numeric validation. pytest checks the loader against small datasets with known expected results. Backend dependencies will be added when their stages begin.

## Structure

```text
app/data.py                 Reusable loading and validation
app/recommender.py          Sparse user-user CF, popularity, genres, groups
scripts/load_movielens.py    Explicit download and validation command
data/                       Downloaded CSV files and upstream README
tests/test_data.py          Offline foundation tests
tests/test_recommender.py   Hand-checkable algorithm tests
notebooks/                  Reserved for later educational exploration
```

## Dataset attribution

Data comes from [MovieLens latest-small, GroupLens Research](https://grouplens.org/datasets/movielens/latest/). Its [README and usage terms](https://files.grouplens.org/datasets/movielens/ml-latest-small-README.html) are also retained locally as `data/README.txt` when downloaded. The latest-small dataset is a development dataset that may change; it is not a fixed research benchmark.

F. Maxwell Harper and Joseph A. Konstan. 2015. The MovieLens Datasets: History and Context. ACM Transactions on Interactive Intelligent Systems 5, 4, Article 19. https://doi.org/10.1145/2827872

## Recommendation engine

```python
from app.data import load_movielens
from app.recommender import build_user_ratings, combine_profiles, recommend

movies, ratings = load_movielens()
historical_users = build_user_ratings(ratings)  # Prepare once, reuse for requests.
profile = {1: 4.5, 2: 2.0}  # MovieLens movie IDs and validated ratings.
recommendations = recommend(profile, historical_users, limit=10)
group = combine_profiles([profile, {2: 4.0, 3: 5.0}])
group_recommendations = recommend(group, historical_users)
```

Functions return `(movie_id, score)` pairs; titles and genres can be looked up in the movies table. Profiles are sparse dictionaries containing only rated movies. Inputs should contain finite ratings within 0.5–5.0 and known movie IDs, as provided by the loader; future application input validation belongs at the application boundary.

Pearson correlation compares only shared movies, centering each user's shared ratings around their shared mean. Fewer than `min_overlap` shared movies (default 2) or zero variance gives similarity zero. `nearest_neighbors` keeps up to `k` positive correlations (default 15), ordered by similarity. Negative and zero correlations do not contribute. When testing a historical user against the historical dataset, pass `exclude_user_id` to avoid selecting that user as their own neighbor; application user IDs are separate.

For each unseen movie, prediction is the target's overall mean plus the similarity-weighted average of neighbors' deviations from their own overall means:

```text
prediction(u, movie) = mean(u)
    + sum(similarity(u, v) * (rating(v, movie) - mean(v)))
      / sum(similarity(u, v))
```

Only selected neighbors who rated that movie enter the sums. Movies need at least `min_neighbors` contributors (default 1). Predictions are clipped to 0.5–5.0 and ranked descending, with movie ID breaking ties. Already-rated movies are excluded.

When no usable predictions exist, `recommend` falls back to historical average ratings with at least `min_rating_count` ratings (default 20, inclusive). Fallback also excludes seen movies and may return an empty list. A short personalized list is returned without filling it with popularity scores. `popular_recommendations` ranks by average, then count, then ID. `genre_recommendations` applies the same ranking to exact pipe-separated genre tokens, ignoring case; unknown genres return an empty list.

Groups average supplied ratings per movie and preserve movies rated by only one member, then use `recommend` on that combined profile. Movies seen by any member are excluded. This simple strategy can hide disagreements and does not guarantee every member likes each recommendation. Pearson based on only two shared movies can be unreliable; increasing overlap and contributor thresholds trades coverage for stronger evidence. CF also cannot recommend movies with no neighbor ratings.

## Next stage

Stage 3 will add SQLite persistence for application users and ratings, keeping them separate from historical MovieLens profiles.
