"""Refresh distribution hashes for deliberately pinned Python requirements."""
import json
from pathlib import Path
import re
from urllib.request import urlopen


def locked(path):
    lines = []
    for line in path.read_text().splitlines():
        match = re.match(r'^([A-Za-z0-9_-]+)==([^ ;\\]+)(.*?)(?:\s*\\)?$', line)
        if not match:
            if line.startswith(('#', '-r ')): lines.append(line)
            continue
        name, version, marker = match.groups()
        marker = marker.strip().removesuffix('\\').strip()
        with urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=30) as response:
            metadata = json.load(response)
        hashes = sorted({item['digests']['sha256'] for item in metadata['urls']})
        if not hashes: raise ValueError(f'No published distributions for {name}')
        lines.append(f'{name}=={version}' + (f' {marker}' if marker else '') + ' \\\n' + ' \\\n'.join('    --hash=sha256:' + digest for digest in hashes))
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    paths = [Path('requirements.txt'), Path('requirements-dev.txt')]
    results = [locked(path) for path in paths]
    for path, result in zip(paths, results): path.write_text(result)
