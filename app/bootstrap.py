"""Opt-in, bounded bootstrap of immutable prepared data; never preprocess ratings."""

from contextlib import contextmanager
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
import tempfile
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

from app.historical import ARRAY_DTYPES, checksum, load_prepared


RELEASE_URL = "https://github.com/aanxnd/movie-recommender/releases/download/data-v1/ml-32m-v1.tar.gz"
RELEASE_SHA256 = "1e7fc9d6c664cff0f697438996e31ed6cf40cd7570aee43e31b814f0e505c303"
FILES = {f"{name}.npy" for name in ARRAY_DTYPES} | {"catalog.json", "manifest.json", "README.txt"}
MAX_DOWNLOAD_BYTES = 200 * 1024**2
MAX_EXTRACTED_BYTES = 600 * 1024**2
IO_TIMEOUT = 30
LOCK_TIMEOUT = 300


class BootstrapError(RuntimeError):
    """Safe error messages contain no URLs, credentials, or transport exceptions."""


def trusted_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and parsed.hostname == "github.com" and
                parsed.port in {None, 443} and not parsed.username and not parsed.password and
                not parsed.query and not parsed.fragment and
                re.fullmatch(r"/aanxnd/movie-recommender/releases/download/[A-Za-z0-9_-][A-Za-z0-9._-]*/ml-32m-v1\.tar\.gz", parsed.path) is not None)
    except ValueError:
        return False


class SafeRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if (parsed.scheme != "https" or parsed.hostname not in {
                "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"
        } or parsed.username or parsed.password or parsed.port not in {None, 443}):
            raise BootstrapError("Untrusted archive redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@contextmanager
def bootstrap_lock(path: Path, timeout: float = LOCK_TIMEOUT):
    """OS locks release on process exit; a bounded wait handles concurrent starters."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise BootstrapError("Prepared-data bootstrap lock timed out") from None
                time.sleep(.1)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def file_state(directory: Path) -> dict:
    return {name: [p.stat().st_size, p.stat().st_mtime_ns] for name in sorted(FILES)
            for p in [directory / name]}


def validate_prepared(directory: Path, *, verify_hashes: bool = False) -> None:
    if (directory.is_symlink() or not directory.is_dir() or
            {p.name for p in directory.iterdir()} != FILES or
            any(p.is_symlink() or not p.is_file() for p in directory.iterdir())):
        raise BootstrapError("Invalid prepared artifact inventory")
    data = None
    try:
        data = load_prepared(directory)
        expected = data.manifest["artifact_checksums"]
        if set(expected) != FILES - {"manifest.json"}:
            raise BootstrapError("Invalid prepared checksum inventory")
        if verify_hashes and any(checksum(directory / name) != value for name, value in expected.items()):
            raise BootstrapError("Prepared artifact checksum mismatch")
    except BootstrapError:
        raise
    except Exception:
        raise BootstrapError("Prepared artifact validation failed") from None
    finally:
        if data is not None:
            data.close()


def marker_path(destination: Path) -> Path:
    return destination.parent / f".{destination.name}.verified.json"


def write_marker(destination: Path, digest: str | None, *, downloaded: bool = False) -> None:
    marker = marker_path(destination)
    with tempfile.NamedTemporaryFile(mode="w", dir=destination.parent, prefix=".verified-", delete=False) as stream:
        temporary = Path(stream.name)
        json.dump({"expected_archive_sha256": digest, "verification": "pinned archive" if downloaded else "existing manifest", "files": file_state(destination)}, stream)
    try:
        os.replace(temporary, marker)
    finally:
        temporary.unlink(missing_ok=True)


def reusable(destination: Path, digest: str | None, *, cache: bool = False) -> bool:
    if not destination.exists():
        return False
    validate_prepared(destination)
    try:
        marker = json.loads(marker_path(destination).read_text())
        if marker.get("expected_archive_sha256") == digest and marker.get("files") == file_state(destination):
            return True
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    # Existing administrator-supplied data is verified against its manifest,
    # without the expensive semantic profile/posting scan.
    validate_prepared(destination, verify_hashes=True)
    if cache:
        write_marker(destination, digest)
    return True


def download_archive(url: str, digest: str, parent: Path) -> Path:
    opener = build_opener(SafeRedirects())
    for attempt in range(3):
        with tempfile.NamedTemporaryFile(dir=parent, prefix=".download-", suffix=".part", delete=False) as stream:
            partial = Path(stream.name)
        try:
            hasher = hashlib.sha256()
            size = 0
            started = time.monotonic()
            with opener.open(url, timeout=IO_TIMEOUT) as response, partial.open("wb") as stream:
                declared = response.headers.get("Content-Length")
                declared = int(declared) if declared is not None else None
                if declared is not None and (declared < 0 or declared > MAX_DOWNLOAD_BYTES):
                    raise BootstrapError("Archive exceeds download limit")
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_DOWNLOAD_BYTES or time.monotonic() - started > 180:
                        raise BootstrapError("Archive download limit exceeded")
                    hasher.update(chunk)
                    stream.write(chunk)
            if declared is not None and size != declared:
                raise BootstrapError("Incomplete archive download")
            if hasher.hexdigest() != digest:
                raise BootstrapError("Archive SHA-256 mismatch")
            return partial
        except BootstrapError:
            partial.unlink(missing_ok=True)
            raise
        except (OSError, URLError, HTTPException, ValueError):
            partial.unlink(missing_ok=True)
            if attempt == 2:
                raise BootstrapError("Archive download failed after bounded retries") from None
            time.sleep(attempt + 1)
        except Exception:
            partial.unlink(missing_ok=True)
            raise BootstrapError("Archive download failed") from None
    raise BootstrapError("Archive download failed")


def extract_archive(archive: Path, staging: Path) -> Path:
    """Inspect the entire bounded inventory before writing any extracted member."""
    seen = set()
    total = 0
    with tarfile.open(archive, "r:gz") as stream:
        members = []
        for member in stream:
            name = member.name.rstrip("/")
            path = PurePosixPath(name)
            if (len(members) >= len(FILES) + 1 or name in seen or path.is_absolute() or
                    ".." in path.parts or "\\" in name or str(path) != name or
                    not (member.isfile() or member.isdir())):
                raise BootstrapError("Unsafe archive member")
            if member.isdir():
                if name != "ml-32m-v1":
                    raise BootstrapError("Unexpected archive directory")
            elif name not in {f"ml-32m-v1/{filename}" for filename in FILES}:
                raise BootstrapError("Unexpected archive file")
            if member.size < 0:
                raise BootstrapError("Invalid archive member size")
            total += member.size
            if total > MAX_EXTRACTED_BYTES:
                raise BootstrapError("Archive exceeds extraction limit")
            seen.add(name)
            members.append(member)
        if {name for name in seen if name != "ml-32m-v1"} != {f"ml-32m-v1/{name}" for name in FILES}:
            raise BootstrapError("Incomplete archive inventory")
        stream.extractall(staging, members=members, filter="data")
    return staging / "ml-32m-v1"


def ensure_prepared(destination: Path, url: str | None = None, digest: str | None = None) -> Path:
    """Reuse local data or explicitly bootstrap a pinned trusted HTTPS release."""
    destination = Path(destination)
    if destination.is_symlink():
        raise BootstrapError("Prepared destination must not be a symlink")
    destination = destination.resolve()
    if url or digest:
        if not url or not trusted_url(url) or not digest or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise BootstrapError("Bootstrap requires a trusted HTTPS release URL and SHA-256")
        digest = digest.lower()
    if not url and destination.exists() and reusable(destination, digest):
        return destination
    if not url:
        raise BootstrapError("Prepared data missing; configure archive URL/checksum or prepare data locally")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with bootstrap_lock(destination.parent / f".{destination.name}.bootstrap.lock"):
        if reusable(destination, digest, cache=True):
            return destination
        archive = None
        try:
            archive = download_archive(url, digest, destination.parent)
            with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".staging-") as temporary:
                extracted = extract_archive(archive, Path(temporary))
                validate_prepared(extracted)
                extracted.rename(destination)
            write_marker(destination, digest, downloaded=True)
        except BootstrapError:
            raise
        except Exception:
            raise BootstrapError("Prepared-data bootstrap failed") from None
        finally:
            if archive is not None:
                archive.unlink(missing_ok=True)
    return destination
