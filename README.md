# Movie Recommender

A learning-focused application being built incrementally from an educational movie recommender. It uses FastAPI, SQLite, and an independently implemented user-user collaborative-filtering engine, with a React frontend.

**Current status: Stage 6 (Docker) complete.** Data loading, recommendations, SQLite persistence, the REST API, the React frontend, and backend Docker packaging are implemented. LensKit is not a dependency.

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

Historical MovieLens users and ratings are reference data for the future engine. Application users and their submitted ratings are stored separately in SQLite. The required MovieLens reference snapshot (`data/movies.csv`, `data/ratings.csv`, and `data/README.txt`) is tracked so fresh clones and CI have the required offline dataset. Generated/local application data, downloaded archives, and the virtual environment remain ignored by Git.

pandas handles CSV tables; NumPy supports numeric validation. pytest checks the loader against small datasets with known expected results. Backend dependencies will be added when their stages begin.

## Structure

```text
app/data.py                 Reusable loading and validation
app/recommender.py          Sparse user-user CF, popularity, genres, groups
app/database.py             SQLite setup and user/rating operations
app/models.py               Users, movie reference IDs, application ratings
scripts/load_movielens.py    Explicit download and validation command
data/                       Downloaded CSV files and upstream README
tests/test_data.py          Offline foundation tests
tests/test_recommender.py   Hand-checkable algorithm tests
tests/test_database.py      Isolated SQLite persistence tests
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

## Application persistence

SQLAlchemy maps Python models to SQLite tables and provides database sessions. Install the updated `requirements.txt` before using this module. The default database is `data/application.db`, resolved relative to the repository rather than the terminal's working directory; generated databases are ignored by Git. Importing the module does not create a database.

```python
from sqlalchemy.orm import Session
from app.database import (
    create_database_engine, create_schema, create_user, get_user_profile,
    register_movies, save_rating,
)
from app.data import load_movielens
from app.recommender import build_user_ratings, recommend

movies, historical_ratings = load_movielens()
engine = create_database_engine()  # Pass a Path to use another SQLite file.
create_schema(engine)
with Session(engine) as session, session.begin():
    register_movies(session, [int(value) for value in movies["movie_id"]])
    user_id = create_user(session).id
    save_rating(session, user_id, int(movies.iloc[0].movie_id), 4.5)

with Session(engine) as session:
    profile = get_user_profile(session, user_id)
    recommendations = recommend(profile, build_user_ratings(historical_ratings))
engine.dispose()
```

Run schema creation and catalog registration at initialization; both are safe to repeat. The `movies` table stores only validated MovieLens IDs for foreign-key checks, without duplicating titles, genres, or historical ratings. Application users have only a generated integer ID, in a separate namespace from MovieLens users.

`get_user` returns a user or `None`. `save_rating` inserts or updates one rating per user/movie pair; ratings must be finite numbers from 0.5 through 5.0 (fractional values are allowed). `get_rating` returns a rating or `None`, `get_user_ratings` returns rows ordered by movie ID, and `get_user_profile` returns the Stage 2 sparse dictionary, including `{}` for an unrated user. Rating operations reject unknown users; saving also rejects unregistered movies. Invalid input raises `ValueError`. Database constraints enforce rating bounds, unique pairs, and references even for direct writes.

Writes belong inside `session.begin()`: successful blocks commit and failed blocks roll back. Keep the returned user ID to retrieve the same user's ratings in a later session. Tests use temporary SQLite files and never the default database.

## REST API

Install the updated requirements (FastAPI, Pydantic, Uvicorn, and HTTPX for API tests), and load MovieLens using the setup commands above. Start the API from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`. Open `http://127.0.0.1:8000/docs` for interactive Swagger documentation, or `/redoc` for reference documentation. FastAPI routes HTTP requests; Pydantic validates JSON and describes response schemas; Uvicorn runs the server. Startup loads the validated CSVs, prepares historical profiles once, creates the SQLite schema, and registers MovieLens IDs. Each database request uses a session and transaction. No dataset download happens at API startup.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | `/health` | Returns `{"status": "ok"}` |
| GET | `/movies/search?q=film&limit=20` | Case-insensitive literal title search; blank or unmatched queries return `[]` |
| GET | `/movies/{movie_id}` | Movie ID, title, and genre list |
| GET | `/movies/decades` | Sorted catalog-derived release decades |
| GET | `/recommendations/popular` | Historical popularity ranking |
| GET | `/recommendations/genre/{genre}` | Whole-token genre ranking; unknown or blank genres return `[]` |
| POST | `/users` | Creates an ID-only user, with no request body; returns 201 |
| GET | `/users/{user_id}` | Retrieves an application user |
| PUT | `/users/{user_id}/ratings/{movie_id}` | Saves or updates `{"rating": 4.5}`; returns 200 |
| GET | `/users/{user_id}/ratings` | Saved ratings ordered by movie ID |
| GET | `/users/{user_id}/recommendations` | Personalized recommendations with existing cold-start fallback |
| POST | `/recommendations/group` | Combines saved profiles from `{"user_ids": [1, 2]}` |

Recommendation endpoints accept `limit` (default 10, range 1–100), `min_rating_count` (default 20, positive), and optional `decade` (a multiple of 10 from 1800 through 2090). The minimum count controls popularity eligibility, including fallback. Search limits range from 1–100. Groups require 2–100 distinct existing application user IDs. Responses contain `movie_id`, `title`, `genres`, `score`, `confidence`, and `method`. Methods are `collaborative_filtering`, `popularity_fallback`, or `popularity`. Application users remain separate from historical users, even when their numeric IDs match.

Unknown users or movies return 404; invalid bodies, IDs, or parameters return 422. Ratings accept finite JSON numbers from 0.5 through 5.0, including fractional values; strings and booleans are rejected. Database failures return a generic 500 response. API tests use synthetic CSVs and temporary SQLite files, never the real application database.

## React frontend (Stage 5)

The JavaScript frontend in `frontend/` uses React for user/search/rating/recommendation state, Vite for development and builds, Tailwind CSS through its Vite plugin for styling, and Lucide React for a few interface icons. Native `fetch()` sends HTTP/JSON requests to the existing FastAPI REST API. All recommendation calculations and persistence remain in Python.

Install Node.js 22.12 or newer (a supported LTS release is recommended), then install frontend dependencies from the repository root:

```powershell
cd frontend
npm ci
```

With Python dependencies installed and MovieLens loaded as described above, run these in separate terminals.

Backend, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Frontend, from the repository root:

```powershell
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173` for the application. The API is at `http://127.0.0.1:8000`, and interactive documentation remains at `http://127.0.0.1:8000/docs`. Vite forwards `/api/*` to FastAPI on port 8000 and removes the `/api` prefix. This keeps browser requests on the same origin during development without changing the backend or adding CORS configuration. The proxy target lives in `frontend/vite.config.js`.

Create an ID-only user and keep its ID, or load an existing application user ID. Search titles, save ratings from 0.5 through 5.0 in half-point steps, and update ratings from search or Saved ratings. Existing fractional backend ratings are displayed and can be preserved. Saved ratings get movie metadata from the existing movie lookup endpoint. Recommendation tabs provide personalized, popular, generic genre, and group requests; group IDs are separated by commas or spaces. JavaScript safely supports user IDs through `Number.MAX_SAFE_INTEGER`; larger IDs are rejected rather than rounded.

Recommendation scores are shown on a five-point scale. Popular and genre scores are historical averages. Personal and group scores use the genre-adjusted CF estimate below, or an explicitly labeled popularity fallback. Confidence is displayed on a 0–1 evidence-strength scale; fallback confidence is absent. A backend-derived release-decade selector applies to every recommendation tab. Changing a user clears the previous profile's views, and saving a rating or changing decades clears recommendation results so they can be requested again.

To check the production bundle, run `npm run build` inside `frontend/`. The result is `frontend/dist/`. `npm run preview` previews that bundle only; the development `/api` proxy is configured for `npm run dev`. The frontend remains independent of the backend Docker image. Public frontend/backend deployment configuration is deferred.

## Backend Docker (Stage 6)

Verified image build, API workflows, same-container restart persistence, and named-volume persistence across replacement containers. The complete Python suite passed with 187 tests and one existing deprecation warning.

Install and start Docker with Linux containers enabled. The build requires `data/movies.csv`, `data/ratings.csv`, and `data/README.txt`, now included in the repository for offline CI verification. The setup command above can validate or refresh these files.

From the repository root:

```powershell
docker build -t movie-recommender-backend .
docker run -p 8000:8000 movie-recommender-backend
```

Port 8000 must be free; stop a local backend using that port before starting the container. Open `http://localhost:8000/health`, `http://localhost:8000/docs`, or `http://localhost:8000/openapi.json`. Run the React frontend separately with `npm run dev` in `frontend/`; its existing `/api` proxy can use this container on port 8000.

The Python 3.14 slim image installs `requirements.txt`, copies `app/` and the two MovieLens CSVs plus upstream README, and runs Uvicorn on `0.0.0.0:8000` without reload. It contains no Node/Vite or React bundle. Startup preserves the existing CSV validation and loads historical ratings without downloading anything. Requirements and the base tag use version ranges/mutable tags; rebuilding later can resolve newer compatible versions.

SQLite is created at `/backend/data/application.db`. Your local database is excluded from the build. Stopping and starting the same container preserves its users and ratings; removing the container discards them unless external storage is mounted.

Optional persistence across replacement containers:

```powershell
docker volume create movie-recommender-data
docker run --name movie-recommender-api -p 8000:8000 --mount type=volume,source=movie-recommender-data,target=/backend/data movie-recommender-backend
```

Docker populates a new empty named volume with the image's MovieLens files. SQLite then lives alongside them in that volume. After stopping and removing the container, reuse the same volume in a replacement container to retain users and ratings. A reused volume also retains its original MovieLens files even if the image is rebuilt with a newer dataset. An empty host bind mount at this path would hide the required CSVs; use the named-volume command above. This stage does not select a public host or configure production persistence.

## Recommendation quality extension

User-user collaborative filtering remains the primary algorithm. Pearson similarity, neighbor selection, and the mean-centered prediction formula above are unchanged. The API uses `recommend_details` to add a secondary genre adjustment and evidence confidence; existing Python `recommend` and `predict_ratings` retain their score-only behavior.

Let `mu` be the target user's mean rating. For genre `g`, sum deviations from `mu` over the user's rated movies containing that genre, then shrink toward zero with three neutral observations:

```text
preference(g) = sum(rating(movie) - mu) / (genre_rating_count + 3)
candidate_preference = average(preference(g) for each candidate genre)
```

Unseen genres contribute zero to the average. Duplicate genre tokens count once; `(no genres listed)` is ignored. Each rated movie contributes its deviation to each of its genres. Preferences describe relative taste: identical ratings give zero preference, and a profile containing only Sci-Fi movies cannot distinguish Sci-Fi preference from its overall rating baseline.

For each candidate, contributing positive neighbors provide evidence using their similarity `s` and the number of shared target/neighbor ratings `overlap`:

```text
E = sum(s * min(overlap / 5, 1))
confidence = E / (E + 3)
adjustment = clip(0.20 * confidence * candidate_preference, -0.35, 0.35)
score = clip(CF_prediction + adjustment, 0.5, 5.0)
baseline = sum(all historical ratings) / number of historical ratings
ranking_score = baseline + confidence * (score - baseline)
```

Named constants in `app/recommender.py` control these defaults; `recommend_details` also accepts `genre_weight`. More positive contributors, stronger similarities, and more overlap generally increase confidence. Sparse/weak evidence gets a smaller genre adjustment. Genre adjustment can favor or penalize a candidate but cannot create a CF prediction for a movie with no supporting neighbors. Confidence is a heuristic measure of CF evidence, **not a calibrated probability of liking a movie**, and does not measure neighbor agreement. Two shared movies can still produce an unreliable Pearson correlation; the overlap factor reduces, rather than eliminates, this weakness.

Personal/group CF results sort by the internal `ranking_score`, while the API and frontend continue reporting the bounded final predicted `score` and unchanged `confidence`. Shrinkage toward the rating-weighted historical mean reduces uncertain high predictions without promoting confidently low predictions. The global baseline is independent of the target and decade; a high target mean would leave weak 5.0 estimates too highly ranked. At baseline 3.5, 5.0 at confidence 0.12 ranks at 3.68, 4.4 at 0.65 ranks at 4.085, and 2.0 at 0.90 ranks at 2.15. This is a ranking heuristic, not a calibrated posterior estimate.

Original CF clipping before genre adjustment remains intact. Equal ranking scores are resolved by final predicted score, then the retained raw CF prediction, then movie ID. Raw extrapolations beyond the rating range only break these ties: they cannot defeat confidence shrinkage or change displayed ratings. The older score-only Python `recommend` retains its original ordering. Popularity and fallback ordering are unchanged, with no CF ranking score or invented confidence.

Release years are parsed only from trailing `(YYYY)` title metadata in the range 1800–2099. `/movies/decades` derives the available decades; no catalog list is stored in React. For example, `?decade=2010` restricts candidates to 2010–2019 before ranking and limiting. Omitting the parameter means All decades, retaining eligibility for titles with unknown years. A selected decade excludes unknown-year titles. Valid decades without eligible results return `[]`.

If there are no usable CF candidates within the selected decade, the API returns popularity averages from that same decade with `method="popularity_fallback"` and `confidence=null`; no genre adjustment is applied. Popular and genre endpoints use `method="popularity"` and null confidence. Short CF lists are not padded. Group recommendations use the existing combined profile, including its averaged genre preferences and shared-rating overlaps, and still exclude movies seen by any member. SQLite and rating-write behavior are unchanged.
