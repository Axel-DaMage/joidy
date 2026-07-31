FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for sqlite-vec and curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user (uid 1000 matches typical host user for dev volume mounts)
RUN addgroup --system --gid 1000 app && adduser --system --uid 1000 --ingroup app app

COPY --chown=app:app . .

USER app

CMD ["/bin/sh", "-c", "rm -rf alembic/versions/__pycache__ && exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-2} --timeout-keep-alive ${UVICORN_TIMEOUT_KEEP_ALIVE:-5} --proxy-headers --forwarded-allow-ips='*'"]
