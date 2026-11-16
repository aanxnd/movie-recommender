"""Pinned, offline reference verification/packaging; no download or application DB."""
import argparse
import gzip
from hashlib import sha256
from pathlib import Path
import sys
import tarfile

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root if (root / 'app').is_dir() else root.parents[1]))
from app.bootstrap import FILES, verify_local

MANIFEST = '2afcd65695fb1dfa16aeb604caa212bdedfb352027e145ac1ec810e5c13199ef'


def verify(directory):
    directory = Path(directory)
    if sha256((directory / 'manifest.json').read_bytes()).hexdigest() != MANIFEST:
        raise ValueError('Pinned reference required')
    verify_local(directory)  # inventory, no symlinks, all pinned file hashes/license


def package(directory, output):
    directory, output = Path(directory), Path(output)
    verify(directory)
    # Exclusive output; no overwrite of an existing archive or staging resource.
    with output.open('xb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w|', format=tarfile.PAX_FORMAT) as archive:
            for name in sorted(FILES):
                path = directory / name
                info = tarfile.TarInfo('ml-32m-v1/' + name)
                info.size, info.mode, info.mtime = path.stat().st_size, 0o644, 0
                with path.open('rb') as stream:
                    archive.addfile(info, stream)
    # Refuse to report completion if source changed while being copied.
    verify(directory)
    verify_archive(output)


def verify_archive(output):
    import json
    hashes, total, manifest = {}, 0, None
    with tarfile.open(output, 'r:gz') as archive:
        for member in archive:
            name = member.name.removeprefix('ml-32m-v1/')
            total += member.size
            if (member.name != 'ml-32m-v1/' + name or name not in FILES or name in hashes
                    or not member.isfile() or total > 600 * 1024**2):
                raise ValueError('Invalid reference archive')
            with archive.extractfile(member) as stream:
                if name == 'manifest.json':
                    raw = stream.read(65537)
                    if len(raw) > 65536: raise ValueError('Invalid manifest')
                    hashes[name], manifest = sha256(raw).hexdigest(), json.loads(raw)
                else:
                    import hashlib
                    hashes[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    if (set(hashes) != FILES or hashes['manifest.json'] != MANIFEST or
            {k: v for k, v in hashes.items() if k != 'manifest.json'} != manifest['artifact_checksums']):
        raise ValueError('Reference archive checksum mismatch')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.output:
            package(args.prepared, args.output)
        else:
            verify(args.prepared)
        print('Pinned reference verified; no publication authorized')
    except Exception:
        raise SystemExit('Reference operation refused; incomplete output must not be used') from None
