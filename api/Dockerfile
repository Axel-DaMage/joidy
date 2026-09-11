ARG PYTHON_VERSION=3.12

# ── deps: build stage with compilers, kept out of the final image ────────────
FROM python:${PYTHON_VERSION}-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Switch apt sources to HTTPS (Fastly 403s on HTTP from Docker build network)
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r requirements.txt

# ── runtime: slim final image ────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Switch apt sources to HTTPS (Fastly 403s on HTTP from Docker build network)
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources

# curl is needed for the container healthcheck
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deps /install /usr/local

# Create non-root user. Defaults to uid/gid 1000 (matches typical host user).
# In development, docker-compose.dev.yml passes the host UID/GID as build args
# so bind-mounted files are written as the host user and never need sudo (#886).
ARG UID=1000
ARG GID=1000
RUN addgroup --system --gid ${GID} app && adduser --system --uid ${UID} --ingroup app app

COPY --chown=app:app . .

# Create the file-logging directory with correct ownership so the app user
# can write /app/data/logs/api.log at runtime (#577).
RUN mkdir -p /app/data/logs && chown -R app:app /app/data

USER app

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=20s \
  CMD curl -f http://localhost:8000/health/ready || exit 1

CMD ["/bin/sh", "-c", "rm -rf alembic/versions/__pycache__ && exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-2} --timeout-keep-alive ${UVICORN_TIMEOUT_KEEP_ALIVE:-5} --proxy-headers --forwarded-allow-ips='*'"]
