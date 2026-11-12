FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    MOVIELENS_PREPARED_DIR=/backend/data/reference/ml-32m-v1

WORKDIR /backend

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.txt

COPY app/ ./app/

RUN useradd --uid 10001 --create-home appuser \
    && mkdir -p /backend/data/reference \
    && chown -R appuser:appuser /backend/data \
    && printf '%s\n' '#!/bin/sh' 'exec python -m app.manage migrate' > /usr/local/bin/movelle-migrate \
    && chmod 0755 /usr/local/bin/movelle-migrate

USER appuser

EXPOSE 8000

CMD ["python", "-m", "app.runtime"]
