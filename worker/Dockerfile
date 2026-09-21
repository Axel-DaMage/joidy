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

# ── deps-dev: stage with dev/test packages ───────────────────────────────────
FROM deps AS deps-dev

COPY requirements-dev.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install-dev -r requirements-dev.txt

# ── runtime-base: minimal base for runtime and development ───────────────────
FROM python:${PYTHON_VERSION}-slim AS runtime-base

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

# Create non-root user. Defaults to uid/gid 1000 (matches typical host user).
# In development, docker-compose.dev.yml passes the host UID/GID as build args
# so bind-mounted files are written as the host user and never need sudo (#886).
ARG UID=1000
ARG GID=1000
RUN addgroup --system --gid ${GID} app && adduser --system --uid ${UID} --ingroup app app

# ── development: for local dev and running tests in containers ──────────────
FROM runtime-base AS development

COPY --from=deps-dev /install-dev /usr/local
COPY --chown=app:app . .

USER app

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
  CMD curl -f http://localhost:8001/health || exit 1

CMD ["python", "main.py"]

# ── production: lean production image with runtime deps only ────────────────
FROM runtime-base AS production

COPY --from=deps /install /usr/local
COPY --chown=app:app . .

USER app

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
  CMD curl -f http://localhost:8001/health || exit 1

CMD ["python", "main.py"]
