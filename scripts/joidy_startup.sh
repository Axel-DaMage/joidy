#!/usr/bin/env bash
# joidy_startup.sh — start the Joidy stack with health checks.
# Location: scripts/joidy_startup.sh (inside the repo; on system installs such
# as AUR it lives at <share>/joidy/scripts/joidy_startup.sh next to joidy.sh).
# Usage: bash scripts/joidy_startup.sh  (or via joidy.service)
set -e

# Resolve the project directory from the script location
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# ─── Wait for the container engine ──────────────────────────────
# A systemd --user unit cannot order on the system docker.service, so the
# engine readiness check lives here instead: poll `docker info` (or
# `podman info` — daemonless, answers immediately) for up to 60s.
ENGINE=""
if command -v docker &>/dev/null; then
    ENGINE="docker"
elif command -v podman &>/dev/null; then
    ENGINE="podman"
fi

if [ -z "$ENGINE" ]; then
    echo "✗ Neither docker nor podman found in PATH — cannot start Joidy." >&2
    exit 1
fi

# Rootless docker under systemd --user: DOCKER_HOST is often absent from the
# manager's environment. If the per-user socket exists, default to it.
if [ "$ENGINE" = "docker" ] && [ -z "${DOCKER_HOST:-}" ]; then
    _sock="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/docker.sock"
    if [ -S "$_sock" ]; then
        export DOCKER_HOST="unix://${_sock}"
    fi
fi

echo "⏳ Waiting for the container engine (${ENGINE})..."
engine_ready=0
for _ in $(seq 1 60); do
    if "$ENGINE" info &>/dev/null; then
        engine_ready=1
        break
    fi
    sleep 1
done

if [ "$engine_ready" -ne 1 ]; then
    echo "✗ ${ENGINE} did not come up within 60s — giving up." >&2
    echo "  Check 'systemctl status ${ENGINE}' (or '${ENGINE}.socket' for rootless)." >&2
    exit 1
fi

# ─── Start the stack via the CLI ────────────────────────────────
# `joidy up` handles the .env bootstrap (generated secrets, JOIDY_ENV_FILE /
# JOIDY_DATA_DIR on read-only installs), port fallback and prebuilt images —
# never call `make dev-d` here: it needs a writable checkout and the dev
# overlay, which breaks on system installs (/usr/share/joidy is read-only).
echo "🚀 Starting Joidy services..."
if [ -f "$SCRIPT_DIR/joidy.sh" ]; then
    bash "$SCRIPT_DIR/joidy.sh" up
elif command -v joidy &>/dev/null; then
    joidy up
else
    echo "✗ joidy CLI not found (looked for $SCRIPT_DIR/joidy.sh and 'joidy' in PATH)." >&2
    exit 1
fi

# ─── Bounded API readiness check ────────────────────────────────
# /health reports the database check too, so first-boot migrations can
# legitimately take a while — poll up to 120s instead of a fixed sleep +
# single shot. `joidy up` may have bumped the host port via its fallback,
# so prefer the port the api container actually published (host:container
# is ${API_PORT}:8000 — the container side is always 8000); fall back to
# $API_PORT or the default.
API_PORT="${API_PORT:-8000}"
COMPOSE_PROJECT="$(basename -- "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]')"
published_port=$("$ENGINE" ps \
    --filter "label=com.docker.compose.project=${COMPOSE_PROJECT}" \
    --filter "label=com.docker.compose.service=api" \
    --format '{{.Ports}}' 2>/dev/null \
    | sed -nE 's/.*:([0-9]+)->8000.*/\1/p' | head -1 || true)
case "$published_port" in ''|*[!0-9]*) ;; *) API_PORT="$published_port" ;; esac
echo "🔍 Waiting for the API health check (up to 120s on :${API_PORT})..."
api_ready=0
for _ in $(seq 1 120); do
    if curl -sf "http://localhost:${API_PORT}/health" 2>/dev/null \
        | grep -qE '"status":\s*"ok"'; then
        api_ready=1
        break
    fi
    sleep 1
done

if [ "$api_ready" -eq 1 ]; then
    echo "✅ API is healthy — Joidy is ready."
else
    echo "⚠️ API did not report healthy on :${API_PORT} within 120s." >&2
    echo "  Inspect the stack with 'joidy status' and 'joidy logs'." >&2
    exit 1
fi
