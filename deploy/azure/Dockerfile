# Existing Azure legacy Dockerfile remains a rollback artifact, never native auth.
FROM scratch AS reference
FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production PORT=8000 HOME=/tmp TMPDIR=/tmp \
    MOVELLE_NATIVE_MODE=native-release MOVELLE_NATIVE_PREPARED_DIR=/backend/data/reference/ml-32m-v1 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
WORKDIR /backend
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.txt \
    && useradd --uid 10001 --create-home appuser
COPY app/ ./app/
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "app.azure_release"]

# Named build context overrides the empty scratch stage. No remote fallback.
# Default release fails without the exact owner-held, checksum-bound 32M input.
FROM runtime AS release
COPY --from=reference / /backend/data/reference/ml-32m-v1/
RUN python -m app.reference --prepared /backend/data/reference/ml-32m-v1
