# Movie Recommender

A learning-focused Python application being built incrementally from an educational movie recommender. The intended application will use FastAPI, SQLite, and an independently implemented user-user collaborative-filtering engine, with a small HTML/JavaScript frontend.

**Current status: Stage 1 (data foundation).** No recommendation engine, database, API, or website has been implemented yet. LensKit is not a dependency.

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
scripts/load_movielens.py    Explicit download and validation command
data/                       Downloaded CSV files and upstream README
tests/test_data.py          Offline foundation tests
notebooks/                  Reserved for later educational exploration
```

## Dataset attribution

Data comes from [MovieLens latest-small, GroupLens Research](https://grouplens.org/datasets/movielens/latest/). Its [README and usage terms](https://files.grouplens.org/datasets/movielens/ml-latest-small-README.html) are also retained locally as `data/README.txt` when downloaded. The latest-small dataset is a development dataset that may change; it is not a fixed research benchmark.

F. Maxwell Harper and Joseph A. Konstan. 2015. The MovieLens Datasets: History and Context. ACM Transactions on Interactive Intelligent Systems 5, 4, Article 19. https://doi.org/10.1145/2827872

## Next stage

Implement readable collaborative filtering with sparse dictionaries, Pearson similarity, explicit neighbor selection and prediction loops, popularity fallback, genre filtering, and hand-checkable algorithm tests.
