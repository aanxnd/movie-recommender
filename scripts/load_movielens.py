"""Explicitly acquire MovieLens Small or official 32M source files."""

import argparse
import hashlib
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data import DEFAULT_DATA_DIR, load_movielens


DATASET_URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
DATASET_32M_URL = "https://files.grouplens.org/datasets/movielens/ml-32m.zip"


def acquire_32m(destination: Path, local_archive: Path | None = None) -> None:
    """Import official 32M files without loading ratings into a DataFrame.

    Full semantic validation is the explicit bounded preparation step.
    """
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    archive_path = local_archive or destination.parent / "ml-32m.zip"
    if local_archive is None and not archive_path.exists():
        partial = archive_path.with_suffix(".zip.part")
        with urlopen(DATASET_32M_URL, timeout=60) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        partial.rename(archive_path)
    expected_md5 = {"movies.csv": "0df90835c19151f9d819d0822e190797",
                    "ratings.csv": "cf12b74f9ad4b94a011f079e26d4270a"}
    with TemporaryDirectory(prefix=".staging-", dir=destination.parent) as temporary:
        staging = Path(temporary)
        with ZipFile(archive_path) as archive:
            for name in ("movies.csv", "ratings.csv", "README.txt"):
                with archive.open(f"ml-32m/{name}") as source, (staging / name).open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                if name in expected_md5:
                    with (staging / name).open("rb") as stream:
                        actual = hashlib.file_digest(stream, "md5").hexdigest()
                    if actual != expected_md5[name]:
                        raise ValueError(f"Official 32M checksum mismatch: {name}")
        staging.rename(destination)
    print(f"Imported official 32M files to {destination}; run scripts/prepare_movielens.py next")


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
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--dataset", choices=("latest-small", "ml-32m"), default="latest-small")
    parser.add_argument("--download", action="store_true", help="Acquire the selected dataset (32M reuses an existing archive and refuses to overwrite source files)")
    parser.add_argument("--archive", type=Path, help="Import a previously downloaded ZIP for the selected dataset")
    args = parser.parse_args()
    args.data_dir = args.data_dir or (DEFAULT_DATA_DIR / "raw" / "ml-32m" if args.dataset == "ml-32m" else DEFAULT_DATA_DIR)
    try:
        if args.dataset == "ml-32m":
            if not args.download and args.archive is None:
                parser.error("32M acquisition requires --download or --archive")
            acquire_32m(args.data_dir, args.archive)
            return
        if args.archive or args.download or not all((args.data_dir / name).is_file() for name in ["movies.csv", "ratings.csv"]):
            download_movielens(args.data_dir, args.archive)
        movies, ratings = load_movielens(args.data_dir)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"MovieLens loading failed: {error}\n")
    print(f"Validated {len(movies):,} movies, {len(ratings):,} ratings, "
          f"and {ratings['user_id'].nunique():,} historical users in {args.data_dir.resolve()}")


if __name__ == "__main__":
    main()
