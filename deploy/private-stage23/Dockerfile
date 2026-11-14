# Explicit alternative image only. Normal Dockerfile/production CMD stay unchanged.
FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production PORT=8000
WORKDIR /backend
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.txt
COPY app/ ./app/
COPY data/prepared/latest-small-v1/ /backend/reference/
COPY deploy/private-stage23/targets.reviewed.json /backend/private-targets.json
RUN useradd --uid 10001 --create-home appuser
ENV MOVELLE_PRIVATE_PREPARED_DIR=/backend/reference MOVELLE_PRIVATE_TARGETS_FILE=/backend/private-targets.json
USER appuser
EXPOSE 8000
CMD ["python", "-m", "app.private_entry"]
