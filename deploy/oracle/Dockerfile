# Separate, dormant native image. Existing Azure/legacy Dockerfile is retained.
FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production PORT=8000 HOME=/tmp TMPDIR=/tmp
WORKDIR /backend
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.txt \
    && useradd --uid 10001 --create-home appuser
COPY app/ ./app/
COPY deploy/oracle/entry.py /backend/oracle-entry.py
COPY deploy/oracle/reference.py /backend/oracle-reference.py
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["python", "/backend/oracle-entry.py"]
CMD ["python", "-m", "app.native_release"]
