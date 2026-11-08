"""Load only the image's checksum-bound MovieLens IMDb companion, never alter reference files."""
import gzip
import hashlib
import json
from pathlib import Path
import re


def bundled_ids(catalog, catalog_checksum, root=None):
    if not catalog_checksum:
        return {}
    root = Path(root) if root else Path(__file__).with_name('resources')
    try:
        pins = json.loads((root / 'movielens-imdb.sources.json').read_text(encoding='utf-8'))
        if not isinstance(pins, dict) or pins.get('schema') != 1 or pins.get('catalog_sha256') != catalog_checksum:
            return {}
        raw = (root / 'movielens-imdb.json.gz').read_bytes()
        if len(raw) > 2 * 1024**2 or hashlib.sha256(raw).hexdigest() != pins.get('file_sha256'):
            return {}
        import io
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            decoded = stream.read(5 * 1024**2 + 1)
        if len(decoded) > 5 * 1024**2:
            return {}
        data = json.loads(decoded)
        if not isinstance(data, dict) or data.get('schema') != 1 or data.get('catalog_sha256') != catalog_checksum:
            return {}
        result = {}
        for mid, imdb in data['links']:
            if (type(mid) is not int or mid not in catalog or mid in result
                    or not isinstance(imdb, str) or not re.fullmatch(r'tt[0-9]{7,10}', imdb)):
                return {}
            result[mid] = imdb
        return result if len(result) == pins['mapped_movies'] else {}
    except (OSError, ValueError, TypeError, KeyError):
        return {}
