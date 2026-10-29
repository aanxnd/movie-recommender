FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8

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
