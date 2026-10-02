"""Download MovieLens small explicitly; validate before copying into data/."""

import argparse
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data import DEFAULT_DATA_DIR, load_movielens


DATASET_URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"


def download_movielens(destination: Path, local_archive: Path | None = None) -> None:
    """Copy only named dataset files, retaining the upstream license README."""
    with TemporaryDirectory() as temporary:
        staging = Path(temporary)
        archive_path = staging / "movielens.zip"
        if local_archive is not None:
            shutil.copyfile(local_archive, archive_path)
        else:
            with urlopen(DATASET_URL, timeout=60) as response, archive_path.open("wb") as output:
                shutil.copyfileobj(response, output)
        with ZipFile(archive_path) as archive:
            for name in ["movies.csv", "ratings.csv", "README.txt"]:
                with archive.open(f"ml-latest-small/{name}") as source:
                    with (staging / name).open("wb") as output:
                        shutil.copyfileobj(source, output)
        load_movielens(staging)
        destination.mkdir(parents=True, exist_ok=True)
        for name in ["movies.csv", "ratings.csv", "README.txt"]:
            shutil.copyfile(staging / name, destination / name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--download", action="store_true", help="Replace existing files with a fresh download")
    parser.add_argument("--archive", type=Path, help="Import a previously downloaded MovieLens small ZIP")
    args = parser.parse_args()
    try:
        if args.archive or args.download or not all((args.data_dir / name).is_file() for name in ["movies.csv", "ratings.csv"]):
            download_movielens(args.data_dir, args.archive)
        movies, ratings = load_movielens(args.data_dir)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"MovieLens loading failed: {error}\n")
    print(f"Validated {len(movies):,} movies, {len(ratings):,} ratings, "
          f"and {ratings['user_id'].nunique():,} historical users in {args.data_dir.resolve()}")


if __name__ == "__main__":
    main()
