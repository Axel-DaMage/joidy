FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Switch apt sources to HTTPS (Fastly 403s on HTTP from Docker build network)
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources

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

# Create the file-logging directory with correct ownership so the app user
# can write /app/data/logs/api.log at runtime (#577).
RUN mkdir -p /app/data/logs && chown -R app:app /app/data

USER app

CMD ["/bin/sh", "-c", "rm -rf alembic/versions/__pycache__ && exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-2} --timeout-keep-alive ${UVICORN_TIMEOUT_KEEP_ALIVE:-5} --proxy-headers --forwarded-allow-ips='*'"]
