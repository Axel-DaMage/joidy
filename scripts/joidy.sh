#!/usr/bin/env bash
# joidy — CLI for managing the Joidy Docker stack.
#
# Installation (Linux/macOS):
#   chmod +x scripts/joidy.sh
#   ln -sf "$(pwd)/scripts/joidy.sh" ~/.local/bin/joidy
#
#   Or copy to /usr/local/bin and set the project path:
#     sudo cp scripts/joidy.sh /usr/local/bin/joidy
#     echo "$HOME/Documents/Repos/Joidy" > ~/.config/joidy/path
#
#   Or export JOIDY_DIR in your shell profile:
#     export JOIDY_DIR="$HOME/Documents/Repos/Joidy"
#
# Usage:
#   joidy up       Start all services (detached)
#   joidy down     Stop all services
#   joidy sleep    Stop heavy services (ai-service, worker)
#   joidy wake     Restart heavy services from hibernation
#   joidy restart  Restart all services
#   joidy status   Show service status
#   joidy logs     Tail logs (all services)
#   joidy logs api Tail logs for a specific service
#   joidy help     Show this help message
#
# Port fallback: if a service's host port is already bound by a foreign
# process, `joidy up` tries up to 5 subsequent ports before aborting (so the
# stack is never left half-started). Ports held by the joidy compose project's
# own containers are reused (idempotent re-runs).

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
  echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $1"
}

print_ok() {
  echo -e "${GREEN}✓${NC} $1"
}

print_warn() {
  echo -e "${YELLOW}⚠${NC} $1"
}

print_err() {
  echo -e "${RED}✗${NC} $1"
}

# Resolve project directory.
# Priority: JOIDY_DIR env var → ~/.config/joidy/path (user) → /etc/joidy/path (system, e.g. AUR) → script location (../)
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

if [ -n "$JOIDY_DIR" ] && [ -d "$JOIDY_DIR" ]; then
  PROJECT_DIR="$JOIDY_DIR"
elif [ -f "$HOME/.config/joidy/path" ]; then
  PROJECT_DIR="$(cat "$HOME/.config/joidy/path")"
elif [ -f "/etc/joidy/path" ]; then
  PROJECT_DIR="$(cat "/etc/joidy/path")"
else
  PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
  echo "Error: docker-compose.yml not found in $PROJECT_DIR" >&2
  echo "Set JOIDY_DIR env var or create ~/.config/joidy/path with the project path." >&2
  exit 1
fi

# Compose project name = lowercased basename of the project dir. Used to tell
# our own containers apart from foreign ones holding a port we want to bind.
COMPOSE_PROJECT="$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]')"

cd "$PROJECT_DIR"

# ─── Container engine detection ───────────────────────────────────
# Detect the engine early so the env bootstrap can make engine-specific
# decisions (e.g. skip DOCKER_GID for Podman rootless, set socket path).
# Priority: docker-compose → docker compose → podman compose → podman-compose.
CONTAINER_ENGINE="docker"
if command -v docker-compose &>/dev/null; then
  DOCKER_CMD="docker-compose"
elif command -v docker &>/dev/null; then
  DOCKER_CMD="docker compose"
elif command -v podman &>/dev/null && podman compose version &>/dev/null 2>&1; then
  DOCKER_CMD="podman compose"
  CONTAINER_ENGINE="podman"
elif command -v podman-compose &>/dev/null; then
  DOCKER_CMD="podman-compose"
  CONTAINER_ENGINE="podman"
else
  echo -e "${RED}✗ Error: Neither docker nor podman was found in PATH.${NC}" >&2
  exit 1
fi

# ─── .env bootstrap ───────────────────────────────────────────────
# Resolve which .env file to use:
# 1. $PROJECT_DIR/.env          (git-clone install — writable)
# 2. ~/.config/joidy/.env        (AUR/system install — project dir is read-only)
# 3. Auto-create from .env.example with generated secrets
ENV_FILE=""
ENV_FILE_ARG=""
CONFIG_DIR_JOIDY="$HOME/.config/joidy"

if [ -f "$PROJECT_DIR/.env" ]; then
  ENV_FILE="$PROJECT_DIR/.env"
elif [ -w "$PROJECT_DIR" ] && [ -f "$PROJECT_DIR/.env.example" ]; then
  # Project dir is writable (git clone) — create .env there
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
  ENV_FILE="$PROJECT_DIR/.env"
  print_status "Created .env from .env.example"
elif [ -f "$PROJECT_DIR/.env.example" ]; then
  # Project dir is read-only (AUR install) — use user config dir
  mkdir -p "$CONFIG_DIR_JOIDY"
  ENV_FILE="$CONFIG_DIR_JOIDY/.env"
  if [ ! -f "$ENV_FILE" ]; then
    cp "$PROJECT_DIR/.env.example" "$ENV_FILE"
    print_status "Created .env in $CONFIG_DIR_JOIDY (project dir is read-only)"
  fi
  ENV_FILE_ARG="--env-file $ENV_FILE"
fi

# Auto-generate required secrets if empty or placeholder
generate_secret() {
  local len="$1"
  if command -v openssl &>/dev/null; then
    openssl rand -hex "$len"
  else
    # Fallback: use /dev/urandom
    head -c "$((len * 2))" /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
  CHANGED=0
  # POSTGRES_PASSWORD
  PG_PW=$(grep -E '^POSTGRES_PASSWORD=' "$ENV_FILE" | cut -d'=' -f2-)
  if [ -z "$PG_PW" ]; then
    NEW_PW=$(generate_secret 24)
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${NEW_PW}|" "$ENV_FILE"
    print_ok "Generated POSTGRES_PASSWORD"
    CHANGED=1
  fi
  # SECRET_KEY
  SK=$(grep -E '^SECRET_KEY=' "$ENV_FILE" | cut -d'=' -f2-)
  if [ -z "$SK" ] || [ "$SK" = "change_this_to_a_random_secret_key" ]; then
    NEW_SK=$(generate_secret 32)
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${NEW_SK}|" "$ENV_FILE"
    print_ok "Generated SECRET_KEY"
    CHANGED=1
  fi
  # GRAFANA_ADMIN_PASSWORD
  GRAFANA_PW=$(grep -E '^GRAFANA_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d'=' -f2-)
  if [ -z "$GRAFANA_PW" ]; then
    NEW_GRAFANA_PW=$(generate_secret 24)
    sed -i "s|^GRAFANA_ADMIN_PASSWORD=.*|GRAFANA_ADMIN_PASSWORD=${NEW_GRAFANA_PW}|" "$ENV_FILE"
    print_ok "Generated GRAFANA_ADMIN_PASSWORD"
    CHANGED=1
  fi
  if [ "$CHANGED" = "1" ]; then
    print_warn "Auto-generated required secrets in $ENV_FILE"
    print_warn "Edit $ENV_FILE to add: GEMINI_API_KEY, OBSIDIAN_VAULT_PATH, etc."
  fi
  # DOCKER_GID — group owning the Docker socket. The API joins it via
  # `group_add` so the web UI (Settings → Servicios) can query and stop/start
  # services. Without it the default is 0 (root), which cannot read
  # /var/run/docker.sock on Linux and the panel reports Docker as unavailable.
  # Skip for Podman: rootless containers already have socket access via UID
  # mapping, so no group_add is needed.
  if [ "$CONTAINER_ENGINE" != "podman" ]; then
    DOCKER_GID_CURRENT=$(grep -E '^DOCKER_GID=' "$ENV_FILE" | cut -d'=' -f2-)
    if [ -z "$DOCKER_GID_CURRENT" ]; then
      DOCKER_SOCK=$(grep -E '^DOCKER_SOCK_PATH=' "$ENV_FILE" | cut -d'=' -f2-)
      [ -z "$DOCKER_SOCK" ] && DOCKER_SOCK="/var/run/docker.sock"
      DETECTED_GID=""
      if [ -S "$DOCKER_SOCK" ]; then
        DETECTED_GID=$(stat -c '%g' "$DOCKER_SOCK" 2>/dev/null || stat -f '%g' "$DOCKER_SOCK" 2>/dev/null || true)
      fi
      if [ -n "$DETECTED_GID" ]; then
        if grep -qE '^#?DOCKER_GID=' "$ENV_FILE"; then
          sed -i "s|^#\?DOCKER_GID=.*|DOCKER_GID=${DETECTED_GID}|" "$ENV_FILE"
        else
          printf '\nDOCKER_GID=%s\n' "$DETECTED_GID" >>"$ENV_FILE"
        fi
        print_ok "Detected Docker socket group (DOCKER_GID=${DETECTED_GID})"
      fi
    fi
  fi
fi

# ─── Expand ~ in OBSIDIAN_VAULT_PATH ───────────────────────────────
# Docker bind mounts do NOT expand `~` — they require absolute host paths.
# The settings UI and Setup Wizard let users enter home-relative paths
# (e.g. ~/Documentos/notas/mi-vault). Expand `~` to $HOME here and export it
# so compose receives an absolute path. The raw value is kept in .env so the
# UI always shows the clean ~/... form the user typed.
if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
  VAULT_RAW=$(grep -E '^OBSIDIAN_VAULT_PATH=' "$ENV_FILE" | head -1 | cut -d'=' -f2-)
  if [ -n "$VAULT_RAW" ]; then
    VAULT_EXPANDED="$VAULT_RAW"
    # Expand leading ~/ or bare ~ to $HOME
    case "$VAULT_RAW" in
      \~/*) VAULT_EXPANDED="${HOME}/${VAULT_RAW#~/}" ;;
      \~)   VAULT_EXPANDED="$HOME" ;;
    esac
    if [ "$VAULT_EXPANDED" != "$VAULT_RAW" ]; then
      print_ok "Expanded OBSIDIAN_VAULT_PATH: ${VAULT_RAW} → ${VAULT_EXPANDED}"
    fi
    # Export so compose uses the expanded value (overrides .env for this run)
    export OBSIDIAN_VAULT_PATH="$VAULT_EXPANDED"
  fi
fi

# ─── Bind-mount sources ───────────────────────────────────────────
# Compose resolves relative volumes against the compose file directory, which
# is read-only on system installs (/usr/share/joidy). Mounting a non-existent
# ./.env made Docker create a *directory* at /app/.env, so every /config
# request returned 500, and ./data was owned by root so the worker could not
# write its event log. Point both at real, writable paths instead.
if [ -n "$ENV_FILE" ]; then
  export JOIDY_ENV_FILE="$ENV_FILE"
fi
if [ -w "$PROJECT_DIR" ]; then
  export JOIDY_DATA_DIR="$PROJECT_DIR/data"
else
  export JOIDY_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/joidy/data"
fi
mkdir -p "$JOIDY_DATA_DIR/db" "$JOIDY_DATA_DIR/uploads" "$JOIDY_DATA_DIR/vault"

# Services that are stopped during hibernation
HIBERNATE_SERVICES="ai-service worker"

# ─── Podman socket setup ──────────────────────────────────────────
# Podman rootless uses a per-user socket at $XDG_RUNTIME_DIR/podman/podman.sock
# (typically /run/user/$UID/podman/podman.sock), owned by the user — no group
# needed. Docker uses /var/run/docker.sock owned by the docker group.
# We set DOCKER_SOCK_PATH so compose mounts the right socket, and skip DOCKER_GID
# detection for Podman since rootless containers already have socket access.
if [ "$CONTAINER_ENGINE" = "podman" ]; then
  PODMAN_SOCK="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/podman/podman.sock"
  if [ -S "$PODMAN_SOCK" ]; then
    export DOCKER_SOCK_PATH="$PODMAN_SOCK"
    # Ensure the env file has the Podman socket path for compose
    if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
      CURRENT_SOCK=$(grep -E '^DOCKER_SOCK_PATH=' "$ENV_FILE" | cut -d'=' -f2-)
      if [ "$CURRENT_SOCK" != "$PODMAN_SOCK" ]; then
        if grep -qE '^#?DOCKER_SOCK_PATH=' "$ENV_FILE"; then
          sed -i "s|^#\?DOCKER_SOCK_PATH=.*|DOCKER_SOCK_PATH=${PODMAN_SOCK}|" "$ENV_FILE"
        else
          printf '\nDOCKER_SOCK_PATH=%s\n' "$PODMAN_SOCK" >>"$ENV_FILE"
        fi
        print_ok "Set DOCKER_SOCK_PATH for Podman ($PODMAN_SOCK)"
      fi
    fi
  else
    print_warn "Podman socket not found at $PODMAN_SOCK"
    print_warn "Enable it with: systemctl --user enable --now podman.socket"
  fi
fi

# Detect the LAN IP address (exclude loopback, docker, virbr, etc.)
get_lan_ip() {
  local ip=""
  # Try ip command first (modern Linux)
  if command -v ip &>/dev/null; then
    ip=$(ip -4 addr show 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' \
      | grep -vE '127\.|172\.1[6-9]\.|172\.2[0-9]\.|172\.3[01]\.|169\.254\.' \
      | head -1)
  fi
  # Fallback to hostname command (macOS / older Linux)
  if [ -z "$ip" ] && command -v hostname &>/dev/null; then
    ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    # Filter out docker/virbr ranges
    echo "$ip" | grep -qE '^172\.|^169\.254\.' && ip=""
  fi
  # Final fallback
  [ -z "$ip" ] && ip="localhost"
  echo "$ip"
}

print_access_url() {
  local port="${FRONTEND_PORT:-3000}"
  local ip
  ip=$(get_lan_ip)
  echo ""
  echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║  Joidy is running at:                        ║${NC}"
  echo -e "${GREEN}║  http://${ip}:${port}${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
}

# Check whether the AI profile should be enabled by reading the .env file.
ai_profile_args() {
  if [ -n "$ENV_FILE" ] && grep -q '^AI_SERVICE_ENABLED=true' "$ENV_FILE" 2>/dev/null; then
    echo "--profile ai"
  fi
}

# ─── Port fallback helpers ─────────────────────────────────────────
# Before `joidy up`, resolve a free host port for each service. If the
# configured port is busy by a foreign process, try up to 5 subsequent ports.
# Ports held by our own compose project's containers are reused (idempotent).
# If no free port is found, abort without running `compose up`.

# Read a port setting: env var → .env file → default.
read_port() {
  local var="$1" default="$2" val=""
  if [ -n "${!var:-}" ]; then
    val="${!var}"
  elif [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
    val=$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d'=' -f2-)
  fi
  [ -z "$val" ] && val="$default"
  echo "$val"
}

# Is anything listening on $1 (TCP, any interface)?
port_in_use() {
  local port="$1"
  if command -v ss &>/dev/null; then
    ss -tlnH 2>/dev/null | awk '{print $4}' | grep -qE ":${port}$"
  elif command -v netstat &>/dev/null; then
    netstat -tlnH 2>/dev/null | awk '{print $4}' | grep -qE ":${port}$"
  else
    return 1 # cannot check — assume free
  fi
}

# Is $1 held by a container of our own compose project? (Docker only)
port_held_by_self() {
  local port="$1"
  [ "$CONTAINER_ENGINE" = "docker" ] || return 1
  command -v docker &>/dev/null || return 1
  docker ps --no-trunc \
    --filter "label=com.docker.compose.project=${COMPOSE_PROJECT}" \
    --format '{{.Ports}}' 2>/dev/null | grep -qE ":${port}->"
}

# Is $1 available for us to bind? (free, or already held by our own stack)
port_available() {
  local port="$1"
  if ! port_in_use "$port"; then
    return 0
  fi
  port_held_by_self "$port"
}

# Find a free port starting at $1, trying up to 5 subsequent ports (6 tries).
# Skips ports already assigned to another joidy service in this run.
# Echoes the chosen port; returns 1 if none free.
find_free_port() {
  local start="$1" port offset p
  for offset in 0 1 2 3 4 5; do
    port=$((start + offset))
    # Skip ports already claimed by another joidy service this run
    for p in "${RESOLVED_PORTS[@]:-}"; do
      [ "$p" = "$port" ] && continue 2
    done
    if port_available "$port"; then
      echo "$port"
      return 0
    fi
  done
  return 1
}

# Resolve free host ports for all 4 services and export them. Aborts (exit 1)
# without invoking compose if any service cannot get a free port.
resolve_ports() {
  local api_def ai_def worker_def frontend_def
  api_def=$(read_port API_PORT 8000)
  ai_def=$(read_port AI_SERVICE_PORT 8002)
  worker_def=$(read_port WORKER_PORT 8001)
  frontend_def=$(read_port FRONTEND_PORT 3000)

  RESOLVED_PORTS=()
  local api ai worker frontend
  api=$(find_free_port "$api_def") || {
    print_err "No free port for api (tried ${api_def}..$((api_def + 5))) — aborting."
    exit 1
  }
  RESOLVED_PORTS+=("$api")
  ai=$(find_free_port "$ai_def") || {
    print_err "No free port for ai-service (tried ${ai_def}..$((ai_def + 5))) — aborting."
    exit 1
  }
  RESOLVED_PORTS+=("$ai")
  worker=$(find_free_port "$worker_def") || {
    print_err "No free port for worker (tried ${worker_def}..$((worker_def + 5))) — aborting."
    exit 1
  }
  RESOLVED_PORTS+=("$worker")
  frontend=$(find_free_port "$frontend_def") || {
    print_err "No free port for frontend (tried ${frontend_def}..$((frontend_def + 5))) — aborting."
    exit 1
  }
  RESOLVED_PORTS+=("$frontend")

  export API_PORT="$api"
  export AI_SERVICE_PORT="$ai"
  export WORKER_PORT="$worker"
  export FRONTEND_PORT="$frontend"

  [ "$api" != "$api_def" ] && print_warn "API_PORT bumped ${api_def}→${api}"
  [ "$ai" != "$ai_def" ] && print_warn "AI_SERVICE_PORT bumped ${ai_def}→${ai}"
  [ "$worker" != "$worker_def" ] && print_warn "WORKER_PORT bumped ${worker_def}→${worker}"
  [ "$frontend" != "$frontend_def" ] && print_warn "FRONTEND_PORT bumped ${frontend_def}→${frontend}"
  return 0
}

cmd_pull() {
  print_status "Pulling latest Joidy images..."
  local profile
  profile="$(ai_profile_args)"
  if [ -n "$profile" ]; then
    $DOCKER_CMD $ENV_FILE_ARG $profile pull || print_warn "Could not pull latest images, using local/cached images."
  else
    $DOCKER_CMD $ENV_FILE_ARG pull || print_warn "Could not pull latest images, using local/cached images."
  fi
  print_ok "Pull complete."
}

cmd_up() {
  print_status "Starting Joidy services..."
  resolve_ports
  local profile
  profile="$(ai_profile_args)"
  if [ -n "$profile" ]; then
    $DOCKER_CMD $ENV_FILE_ARG $profile up -d
  else
    $DOCKER_CMD $ENV_FILE_ARG up -d
  fi
  print_status "Waiting for services to stabilize..."
  sleep 5
  cmd_status
  print_access_url
}

cmd_down() {
  print_status "Stopping all Joidy services..."
  $DOCKER_CMD $ENV_FILE_ARG down
  print_ok "All services stopped."
}

cmd_sleep() {
  print_status "Hibernating heavy services (ai-service, worker)..."
  for svc in $HIBERNATE_SERVICES; do
    # Check if the service is running by looking at docker compose ps output
    if $DOCKER_CMD $ENV_FILE_ARG ps "$svc" 2>/dev/null | grep -q "$svc"; then
      $DOCKER_CMD $ENV_FILE_ARG stop "$svc"
      print_ok "Stopped $svc"
    else
      print_warn "$svc is already stopped"
    fi
  done
  echo ""
  print_ok "Hibernation complete. API, frontend, and database are still running."
  echo "  Use 'joidy wake' to restart heavy services."
}

cmd_wake() {
  print_status "Waking heavy services from hibernation..."
  local profile
  profile="$(ai_profile_args)"
  for svc in $HIBERNATE_SERVICES; do
    # Check if the service is NOT running (use -a to include stopped containers)
    if $DOCKER_CMD $ENV_FILE_ARG $profile ps -a "$svc" 2>/dev/null | grep -q "$svc"; then
      if $DOCKER_CMD $ENV_FILE_ARG $profile ps "$svc" 2>/dev/null | grep -q "$svc"; then
        print_warn "$svc is already running"
      else
        $DOCKER_CMD $ENV_FILE_ARG $profile start "$svc"
        print_ok "Started $svc"
      fi
    else
      print_warn "$svc container not found"
    fi
  done
  echo ""
  print_ok "Wake complete."
}

cmd_restart() {
  print_status "Restarting all Joidy services..."
  local profile
  profile="$(ai_profile_args)"
  if [ -n "$profile" ]; then
    $DOCKER_CMD $ENV_FILE_ARG $profile restart
  else
    $DOCKER_CMD $ENV_FILE_ARG restart
  fi
  print_ok "All services restarted."
  print_access_url
}

cmd_status() {
  print_status "Joidy service status:"
  echo ""
  $DOCKER_CMD $ENV_FILE_ARG ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || $DOCKER_CMD $ENV_FILE_ARG ps
}

cmd_logs() {
  local svc="${1:-}"
  if [ -n "$svc" ]; then
    $DOCKER_CMD $ENV_FILE_ARG logs -f "$svc"
  else
    $DOCKER_CMD $ENV_FILE_ARG logs -f
  fi
}

cmd_help() {
  cat <<'HELP'
joidy — Manage the Joidy Docker stack

Usage:
  joidy up         Start all services (detached)
  joidy down       Stop all services
  joidy sleep      Stop heavy services (ai-service, worker) — hibernation
  joidy wake       Restart heavy services from hibernation
  joidy restart    Restart all services
  joidy status     Show service status
  joidy pull       Pull latest images
  joidy logs       Tail logs (all services)
  joidy logs api   Tail logs for a specific service
  joidy help       Show this help message

On first run, .env is auto-created from .env.example with generated
POSTGRES_PASSWORD, SECRET_KEY, and GRAFANA_ADMIN_PASSWORD.
For AUR installs (read-only /usr/share/joidy), .env is stored in
~/.config/joidy/.env. Edit it to add GEMINI_API_KEY, OBSIDIAN_VAULT_PATH, etc.

The project directory is auto-detected from the script location.

Port fallback: `joidy up` checks the host ports for api (8000), ai-service
(8002), worker (8001) and frontend (3000). If a port is already bound by a
foreign process, it tries up to 5 subsequent ports; if none are free, it
aborts without starting any service (no half-started stack). Ports held by
joidy's own containers are reused, so re-running `joidy up` is idempotent.
HELP
}

# Main
case "${1:-help}" in
  up)       cmd_up ;;
  down)     cmd_down ;;
  sleep)    cmd_sleep ;;
  wake)     cmd_wake ;;
  restart)  cmd_restart ;;
  status)   cmd_status ;;
  pull)     cmd_pull ;;
  logs)     cmd_logs "${2:-}" ;;
  help|--help|-h) cmd_help ;;
  *)
    print_err "Unknown command: $1"
    echo ""
    cmd_help
    exit 1
    ;;
esac
