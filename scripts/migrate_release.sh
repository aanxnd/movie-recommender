#!/usr/bin/env bash
# Only the protected release job supplies these variables. Never echo their values.
set +x
set -euo pipefail

if [[ -z ${DATABASE_URL:-} || ${APP_ENV:-} != production || -z ${CORS_ALLOWED_ORIGINS:-} ]]; then
  echo '::error::Production migration configuration is missing or invalid; deployment blocked.'
  exit 1
fi
if [[ ! ${IMAGE:-} =~ ^ghcr\.io/aanxnd/movie-recommender@sha256:[a-f0-9]{64}$ ]]; then
  echo '::error::Migration requires the verified release image digest; deployment blocked.'
  exit 1
fi
if ! docker pull "$IMAGE" >/dev/null 2>&1; then
  echo '::error::Cannot pull the verified release image; deployment blocked.'
  exit 1
fi

container="movelle-migration-$$-$RANDOM"
cleanup() { docker rm --force "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT
trap 'exit 1' INT TERM

# Pass environment names, never secret values in arguments or files. No host mounts.
# Preflight uses the image's own validators without starting ASGI or loading data.
if ! timeout --signal=TERM --kill-after=15s 300s docker run --rm \
  --name "$container" --pull=never --read-only --log-driver=none \
  --cap-drop=ALL --security-opt=no-new-privileges \
  --env DATABASE_URL --env APP_ENV --env CORS_ALLOWED_ORIGINS \
  --entrypoint /bin/sh "$IMAGE" -ec '
    python -c "from app.config import validate; validate(); from app.main import cors_origins; cors_origins()"
    exec /usr/local/bin/movelle-migrate
  ' >/dev/null 2>&1; then
  echo '::error::Production migration failed or timed out; deployment blocked. Check configuration and connectivity privately.'
  exit 1
fi
echo 'Production migration succeeded for the verified release image.'
