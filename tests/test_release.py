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
    assert 'az containerapp job' not in release and 'MIGRATION_JOB' not in release
    assert 'environment: production' in release
    assert 'DATABASE_URL: ${{ secrets.PRODUCTION_DATABASE_URL }}' in release
    assert 'APP_ENV: production' in release
    assert 'CORS_ALLOWED_ORIGINS: ${{ vars.CORS_ALLOWED_ORIGINS }}' in release
    assert 'run: bash scripts/migrate_release.sh' in release
    assert 'packages: read' in release
    assert release.index('Reject stale release') < release.index('Migrate using') < release.index('uses: azure/login@')
    assert 'continue-on-error' not in release and 'always()' not in release
    migration = re.search(r'      - name: Migrate using.*?(?=\n      - )', release, re.S).group()
    assert release.count('secrets.PRODUCTION_DATABASE_URL') == 1
    assert 'secrets.PRODUCTION_DATABASE_URL' in migration
    assert 'timeout-minutes: 7' in migration
    assert release.index('Reject stale release') < release.rindex('uses: docker/login-action@') < release.index('Migrate using')
    assert 'digest: ${{ steps.image.outputs.digest }}' in release
    assert 'IMAGE: ghcr.io/aanxnd/movie-recommender@${{ steps.image.outputs.digest }}' in release
    assert 'IMAGE: ghcr.io/aanxnd/movie-recommender@${{ needs.publish.outputs.digest }}' in release
    assert 'imageToDeploy: ${{ env.IMAGE }}' in release
    assert ':latest' not in release
    for text in (ci, release):
        for action in re.findall(r'uses: ([^\s]+)', text):
            if action.startswith('./'): continue
            assert re.search(r'@[a-f0-9]{40}$', action), action
