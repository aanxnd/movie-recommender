"""Structural release invariants; cloud execution remains an operator check."""
from pathlib import Path
import re


def test_release_is_manual_verified_serialized_and_digest_based():
    release = Path('.github/workflows/publish-image.yml').read_text(encoding='utf-8-sig')
    ci = Path('.github/workflows/tests.yml').read_text()
    assert 'workflow_dispatch:' in release and '\n  push:' not in release
    assert 'needs: verify' in release and 'needs: publish' in release
    assert 'uses: ./.github/workflows/tests.yml' in release and 'workflow_call:' in ci
    assert 'cancel-in-progress: false' in release
    assert 'git ls-remote origin refs/heads/main' in release
    assert 'movie-recommender@${{' in release
    assert release.index('Migrate using') < release.index('Deploy tested')
    assert 'if [ "$status" = Failed ]; then exit 1' in release
    assert ':latest' not in release
    for text in (ci, release):
        for action in re.findall(r'uses: ([^\s]+)', text):
            if action.startswith('./'): continue
            assert re.search(r'@[a-f0-9]{40}$', action), action
