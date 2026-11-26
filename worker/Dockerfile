# Base image pinned by multi-arch index digest (#1391). Dependabot (docker
# ecosystem) bumps tag + digest together; both stages must use the same reference.

# This deps/runtime skeleton is intentionally mirrored across api/Dockerfile,
# ai-service/Dockerfile and worker/Dockerfile — keep the shared stages in sync
# when editing. A shared base image was rejected (#1555): every build entry
# point uses a per-service context (`docker build ./<svc>`, the dev overlay,
# CI and publish.yml), so a common FROM would add a published image plus build
# ordering for no real size or cache win.

# ── deps: build stage with compilers, kept out of the final image ────────────
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS deps

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

COPY requirements.txt requirements-dev.txt ./

# Dev/test tooling is opt-in: production builds (the default) ship runtime
# deps only, while docker-compose.dev.yml passes INSTALL_DEV=true so dev
# containers can run pytest/ruff/mypy in-container (#999).
ARG INSTALL_DEV=false
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ "$INSTALL_DEV" = "true" ]; then \
        pip install --prefix=/install -r requirements-dev.txt; \
    else \
        pip install --prefix=/install -r requirements.txt; \
    fi

# ── runtime: slim final image ────────────────────────────────────────────────
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS runtime

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

USER app

# Keep in sync with the docker-compose.yml healthcheck — the compose override
# wins at runtime; this is only the default for a bare `docker run` (#1555).
HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=15s \
  CMD curl -f http://localhost:8001/health || exit 1

CMD ["python", "main.py"]
