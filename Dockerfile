FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MOVIELENS_PREPARED_DIR=/backend/data/reference/ml-32m-v1

WORKDIR /backend

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN useradd --uid 10001 --create-home appuser \
    && mkdir -p /backend/data/reference \
    && chown -R appuser:appuser /backend/data

USER appuser

EXPOSE 8000

CMD ["python", "-m", "app.runtime"]
