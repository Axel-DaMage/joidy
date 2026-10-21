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
#   joidy idle enable [--idle-hibernate-db]
#                  Start the idle watchdog (auto-sleep when unused)
#   joidy idle disable  Stop the watchdog (services untouched)
#   joidy idle status   Watcher state, last activity, time until sleep
#   joidy backup   Write a compressed pg_dump to the backups dir
#   joidy restore <file> [--force]   Restore a dump into the database
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
mkdir -p "$JOIDY_DATA_DIR/db" "$JOIDY_DATA_DIR/uploads" "$JOIDY_DATA_DIR/vault" "$JOIDY_DATA_DIR/backups"

# Compose interpolates ${UID}/${GID} for the `backup` service so its dumps land
# on the bind mount owned by the host user instead of root. Export them here;
# unset they default to 0:0 in docker-compose.yml.
export UID
export GID="${GID:-$(id -g)}"

# Services that are stopped during hibernation
HIBERNATE_SERVICES="ai-service worker"

# Idle-watchdog state directory. Honors the same writable-dir fallback as
# JOIDY_DATA_DIR (read-only installs land under ~/.local/share/joidy/data).
IDLE_STATE_DIR="${JOIDY_DATA_DIR}/idle"

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

# Check which compose profiles should be enabled by reading the .env file.
#   ai      — opt-in: AI_SERVICE_ENABLED=true
#   backup  — opt-out: enabled by default; BACKUP_ENABLED=false disables it.
#             The backup sidecar reuses the postgres image, so it costs ~0 MB
#             of extra pull and only a few MB of RAM while idle.
profile_args() {
  local args=""
  if [ -n "$ENV_FILE" ] && grep -q '^AI_SERVICE_ENABLED=true' "$ENV_FILE" 2>/dev/null; then
    args="--profile ai"
  fi
  local backup_flag=""
  if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
    backup_flag=$(grep -E '^BACKUP_ENABLED=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d'=' -f2-)
  fi
  if [ "$backup_flag" != "false" ]; then
    args="${args:+$args }--profile backup"
  fi
  echo "$args"
}

# ─── Port fallback helpers ─────────────────────────────────────────
# Before `joidy up`, resolve a free host port for each service. If the
# configured port is busy by a foreign process, try up to 5 subsequent ports.
# Ports held by our own compose project's containers are reused (idempotent).
# If no free port is found, abort without running `compose up`.

# Read a setting: env var → .env file → default.
read_setting() {
  local var="$1" default="$2" val=""
  if [ -n "${!var:-}" ]; then
    val="${!var}"
  elif [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
    val=$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d'=' -f2-)
  fi
  [ -z "$val" ] && val="$default"
  echo "$val"
}

# Read a port setting: env var → .env file → default.
read_port() {
  read_setting "$@"
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
  profile="$(profile_args)"
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
  profile="$(profile_args)"
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
  profile="$(profile_args)"
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
  # If the idle watchdog put the stack to sleep, restore the other services
  # it recorded (frontend, postgres, ...) that the heavy-services loop above
  # does not cover — `joidy wake` restores the pre-sleep set.
  if [ -f "$IDLE_STATE_DIR/pre_sleep_services" ]; then
    idle_restore_state
    print_ok "Restored services recorded before idle sleep."
  fi
  # Reset the idle timer so a running watcher does not re-sleep immediately.
  if [ -d "$IDLE_STATE_DIR" ]; then
    idle_now >"$IDLE_STATE_DIR/last_activity" 2>/dev/null || true
  fi
  print_ok "Wake complete."
}

cmd_restart() {
  print_status "Restarting all Joidy services..."
  local profile
  profile="$(profile_args)"
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

# ─── Idle watchdog (auto-sleep) ─────────────────────────────────
# `joidy idle enable` detaches a watcher (`joidy idle run`, also the ExecStart
# of the optional systemd user unit scripts/joidy-idle-watchdog.service) that
# polls cheap usage signals every JOIDY_IDLE_POLL_SECONDS (default 60):
#   - established TCP connections on the published frontend / api /
#     ai-service / worker ports — real HTTP usage; the in-container
#     healthchecks hit loopback and never appear on the host socket table
#   - active PostgreSQL sessions (pg_stat_activity state='active' — also
#     covers worker job runs, which hold active queries)
#   - file changes under the Obsidian vault
# After JOIDY_IDLE_TIMEOUT minutes (default 15, from .env) with no signal the
# watcher snapshots the running services into pre_sleep_services, runs the
# existing `joidy sleep` path, and additionally stops the frontend (the
# heaviest idle CPU consumer — #860). postgres stays up for data safety;
# `joidy idle enable --idle-hibernate-db` opts into stopping it too. New
# activity while asleep restores the recorded set automatically; `joidy wake`
# does the same on demand.

idle_now() { date +%s; }

idle_log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Format an epoch as a local timestamp (GNU date -d / BSD date -r).
idle_fmt_epoch() {
  date -d "@$1" '+%Y-%m-%d %H:%M:%S' 2>/dev/null \
    || date -r "$1" '+%Y-%m-%d %H:%M:%S' 2>/dev/null \
    || echo "$1"
}

idle_last_activity() {
  if [ -f "$IDLE_STATE_DIR/last_activity" ]; then
    cat "$IDLE_STATE_DIR/last_activity"
  else
    idle_now
  fi
}

idle_watcher_alive() {
  local pid
  [ -f "$IDLE_STATE_DIR/watcher.pid" ] || return 1
  pid=$(cat "$IDLE_STATE_DIR/watcher.pid" 2>/dev/null) || return 1
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

# Service names of currently running compose services (one per line).
idle_running_services() {
  local profile out
  profile="$(ai_profile_args)"
  out=$($DOCKER_CMD $ENV_FILE_ARG $profile ps --services --filter status=running 2>/dev/null || true)
  if [ -z "$out" ]; then
    # Fallback for engines without `ps --services`: match known names in `ps`.
    out=$($DOCKER_CMD $ENV_FILE_ARG $profile ps 2>/dev/null \
      | grep -oE 'postgres|ai-service|worker|frontend|api' | sort -u || true)
  fi
  echo "$out"
}

idle_is_running() {
  idle_running_services | grep -qx "$1"
}

# Signal 1: established TCP connection on any published service port.
# Only the server side (local address = our port) counts. An open browser tab
# (keep-alive / HMR websocket) is therefore treated as activity — sleeping
# while the UI is open in a tab would be wrong anyway.
idle_tcp_activity() {
  local port
  for port in "$@"; do
    if command -v ss >/dev/null 2>&1; then
      if ss -tnH state established 2>/dev/null \
          | awk -v p="$port" '{n=split($4,a,":"); if (a[n]==p) f=1} END{exit !f}'; then
        return 0
      fi
    elif command -v netstat >/dev/null 2>&1; then
      # BSD netstat prints local addr as host.port (e.g. 127.0.0.1.3000).
      if netstat -an 2>/dev/null \
          | awk -v p="$port" '$NF=="ESTABLISHED"{n=split($4,a,/[.:]/); if (a[n]==p) f=1} END{exit !f}'; then
        return 0
      fi
    fi
  done
  return 1
}

# Signal 2: an active client session on postgres (pool idles don't count —
# only state='active', excluding the probe itself).
idle_db_activity() {
  local pg_user pg_db n
  idle_is_running postgres || return 1
  pg_user=$(read_port POSTGRES_USER joidy)
  pg_db=$(read_port POSTGRES_DB joidy)
  n=$($DOCKER_CMD $ENV_FILE_ARG exec -T postgres psql -U "$pg_user" -d "$pg_db" -tAc \
      "SELECT count(*) FROM pg_stat_activity WHERE state='active' AND pid<>pg_backend_pid()" \
      2>/dev/null | tr -d '[:space:]')
  case "$n" in ''|*[!0-9]*) return 1 ;; esac
  [ "$n" -gt 0 ]
}

# Signal 3: a file under the vault changed since the previous poll
# (`find -newer` + a marker file — portable to BSD find on macOS).
idle_vault_activity() {
  local vault="${OBSIDIAN_VAULT_PATH:-$JOIDY_DATA_DIR/vault}"
  local marker="$IDLE_STATE_DIR/vault.marker"
  local hit=""
  if [ -d "$vault" ] && [ -f "$marker" ]; then
    hit=$(find "$vault" -type f -newer "$marker" -print -quit 2>/dev/null)
  fi
  touch "$marker" 2>/dev/null || true
  [ -n "$hit" ]
}

idle_any_activity() {
  local ports
  ports="$(read_port FRONTEND_PORT 3000) $(read_port API_PORT 8000) \
$(read_port AI_SERVICE_PORT 8002) $(read_port WORKER_PORT 8001)"
  idle_tcp_activity $ports && return 0
  idle_db_activity && return 0
  idle_vault_activity && return 0
  return 1
}

# Snapshot running services, then sleep via the existing `joidy sleep` path
# plus the frontend (and postgres only when --idle-hibernate-db was given).
idle_do_sleep() {
  local hibernate_db="$1"
  local profile running
  profile="$(ai_profile_args)"
  running="$(idle_running_services)"
  if [ -z "$(echo "$running" | tr -d '[:space:]')" ]; then
    idle_log "idle timeout reached but no services running — nothing to sleep"
    idle_now >"$IDLE_STATE_DIR/last_activity"
    return 0
  fi
  # shellcheck disable=SC2086 # intentional word-split of the service list
  printf '%s\n' $running >"$IDLE_STATE_DIR/pre_sleep_services"
  idle_log "idle timeout reached — sleeping (was running: $(echo "$running" | tr '\n' ' '), hibernate_db=$hibernate_db)"
  cmd_sleep || true
  if echo "$running" | grep -qx frontend; then
    $DOCKER_CMD $ENV_FILE_ARG $profile stop frontend >/dev/null 2>&1 \
      && idle_log "stopped frontend" || true
  fi
  if [ "$hibernate_db" = "1" ] && echo "$running" | grep -qx postgres; then
    $DOCKER_CMD $ENV_FILE_ARG $profile stop postgres >/dev/null 2>&1 \
      && idle_log "stopped postgres (--idle-hibernate-db)" || true
  fi
  idle_now >"$IDLE_STATE_DIR/slept"
  idle_log "sleep complete — wake with 'joidy wake' or any new activity"
}

# Restart the services recorded before the idle sleep, in dependency order.
# Shared by `joidy wake` and the watcher's auto-restore on new activity.
idle_restore_state() {
  local file="$IDLE_STATE_DIR/pre_sleep_services"
  local profile running svc
  profile="$(ai_profile_args)"
  running="$(idle_running_services)"
  if [ -f "$file" ]; then
    for svc in postgres api frontend worker ai-service; do
      grep -qx "$svc" "$file" 2>/dev/null || continue
      echo "$running" | grep -qx "$svc" && continue
      if $DOCKER_CMD $ENV_FILE_ARG $profile start "$svc" >/dev/null 2>&1; then
        idle_log "restored $svc"
      else
        idle_log "WARN: could not start $svc"
      fi
    done
    # Any recorded service outside the known list (future services).
    while IFS= read -r svc; do
      case "$svc" in postgres|api|frontend|worker|ai-service|'') continue ;; esac
      echo "$running" | grep -qx "$svc" && continue
      $DOCKER_CMD $ENV_FILE_ARG $profile start "$svc" >/dev/null 2>&1 \
        && idle_log "restored $svc" || true
    done <"$file"
    rm -f "$file"
  fi
  rm -f "$IDLE_STATE_DIR/slept"
  idle_now >"$IDLE_STATE_DIR/last_activity"
}

# Foreground watcher loop. Spawned detached by `joidy idle enable`; also the
# ExecStart of scripts/joidy-idle-watchdog.service (systemd --user).
cmd_idle_run() {
  mkdir -p "$IDLE_STATE_DIR"
  # Refuse to run a second watcher instance.
  if [ -f "$IDLE_STATE_DIR/watcher.pid" ]; then
    local old_pid
    old_pid=$(cat "$IDLE_STATE_DIR/watcher.pid" 2>/dev/null || true)
    if [ -n "$old_pid" ] && [ "$old_pid" != "$$" ] && kill -0 "$old_pid" 2>/dev/null; then
      echo "idle watcher already running (pid $old_pid) — exiting" >&2
      exit 0
    fi
  fi
  echo "$$" >"$IDLE_STATE_DIR/watcher.pid"
  trap 'rm -f "$IDLE_STATE_DIR/watcher.pid"; exit 0' TERM INT

  local timeout_min poll_s hibernate_db
  timeout_min=$(read_port JOIDY_IDLE_TIMEOUT 15)
  poll_s=$(read_port JOIDY_IDLE_POLL_SECONDS 60)
  hibernate_db=0
  if [ -f "$IDLE_STATE_DIR/watcher.conf" ]; then
    . "$IDLE_STATE_DIR/watcher.conf"
  fi
  hibernate_db="${IDLE_HIBERNATE_DB:-$hibernate_db}"
  # Numeric sanity — fall back to defaults on garbage values.
  case "$timeout_min" in ''|*[!0-9]*) timeout_min=15 ;; esac
  case "$poll_s" in ''|*[!0-9]*) poll_s=60 ;; esac

  [ -f "$IDLE_STATE_DIR/last_activity" ] || idle_now >"$IDLE_STATE_DIR/last_activity"
  idle_log "watcher started (pid $$, timeout=${timeout_min}m, poll=${poll_s}s, hibernate_db=$hibernate_db)"

  while :; do
    if idle_any_activity; then
      idle_now >"$IDLE_STATE_DIR/last_activity"
      if [ -f "$IDLE_STATE_DIR/slept" ]; then
        idle_log "activity detected while asleep — restoring services"
        idle_restore_state
        idle_log "restore complete"
      fi
    elif [ ! -f "$IDLE_STATE_DIR/slept" ]; then
      local now last
      now=$(idle_now)
      last=$(idle_last_activity)
      if [ $((now - last)) -ge $((timeout_min * 60)) ]; then
        idle_do_sleep "$hibernate_db"
      fi
    fi
    sleep "$poll_s" || true
  done
}

cmd_idle_enable() {
  local hibernate_db=0 arg
  for arg in "$@"; do
    case "$arg" in
      --idle-hibernate-db) hibernate_db=1 ;;
      *) print_err "Unknown option: $arg"; return 1 ;;
    esac
  done
  mkdir -p "$IDLE_STATE_DIR"
  if idle_watcher_alive; then
    print_warn "Idle watcher already running (pid $(cat "$IDLE_STATE_DIR/watcher.pid" 2>/dev/null))"
    return 0
  fi
  printf 'IDLE_HIBERNATE_DB=%s\n' "$hibernate_db" >"$IDLE_STATE_DIR/watcher.conf"
  [ -f "$IDLE_STATE_DIR/last_activity" ] || idle_now >"$IDLE_STATE_DIR/last_activity"
  # Re-exec the resolved script path so this works both for repo checkouts
  # and single-file installs (/usr/local/bin/joidy).
  local self
  self="$(readlink -f "$0" 2>/dev/null || true)"
  [ -f "$self" ] || self="$0"
  nohup bash "$self" idle run </dev/null >>"$IDLE_STATE_DIR/watcher.log" 2>&1 &
  local pid=$!
  disown "$pid" 2>/dev/null || true
  echo "$pid" >"$IDLE_STATE_DIR/watcher.pid"
  local extra="frontend"
  [ "$hibernate_db" = "1" ] && extra="frontend, postgres"
  print_ok "Idle watcher started (pid $pid)"
  echo "  Sleeps the stack after $(read_port JOIDY_IDLE_TIMEOUT 15) min without activity"
  echo "  (via 'joidy sleep' + ${extra}). State: $IDLE_STATE_DIR"
  echo "  Inspect with 'joidy idle status', stop with 'joidy idle disable'."
}

cmd_idle_disable() {
  local pid i
  if ! idle_watcher_alive; then
    print_warn "Idle watcher is not running"
    rm -f "$IDLE_STATE_DIR/watcher.pid"
    return 0
  fi
  pid=$(cat "$IDLE_STATE_DIR/watcher.pid" 2>/dev/null)
  kill "$pid" 2>/dev/null || true
  for i in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$IDLE_STATE_DIR/watcher.pid"
  print_ok "Idle watcher stopped (the stack was left untouched)."
}

cmd_idle_status() {
  local timeout_min poll_s last now remaining
  timeout_min=$(read_port JOIDY_IDLE_TIMEOUT 15)
  poll_s=$(read_port JOIDY_IDLE_POLL_SECONDS 60)
  echo ""
  if idle_watcher_alive; then
    print_ok "Idle watcher: RUNNING (pid $(cat "$IDLE_STATE_DIR/watcher.pid" 2>/dev/null), poll ${poll_s}s)"
  else
    print_warn "Idle watcher: stopped — enable with 'joidy idle enable'"
  fi
  echo "  Timeout:       ${timeout_min} min (JOIDY_IDLE_TIMEOUT)"
  if [ -f "$IDLE_STATE_DIR/watcher.conf" ] && grep -q 'IDLE_HIBERNATE_DB=1' "$IDLE_STATE_DIR/watcher.conf"; then
    echo "  Hibernate DB:  yes (--idle-hibernate-db)"
  fi
  if [ -f "$IDLE_STATE_DIR/last_activity" ]; then
    last=$(cat "$IDLE_STATE_DIR/last_activity" 2>/dev/null)
    case "$last" in ''|*[!0-9]*) last=$(idle_now) ;; esac
    now=$(idle_now)
    echo "  Last activity: $(idle_fmt_epoch "$last")"
    if [ -f "$IDLE_STATE_DIR/slept" ]; then
      echo "  Stack state:   ASLEEP since $(idle_fmt_epoch "$(cat "$IDLE_STATE_DIR/slept" 2>/dev/null)")"
      echo "                 ('joidy wake' restores the recorded services)"
    else
      remaining=$((timeout_min * 60 - (now - last)))
      [ "$remaining" -lt 0 ] && remaining=0
      echo "  Sleep in:      ${remaining}s (≈$((remaining / 60))m) if no new activity"
    fi
  else
    echo "  Last activity: (not recorded yet)"
  fi
  echo ""
}

cmd_idle() {
  local sub="${1:-status}"
  case "$sub" in
    enable)  shift; cmd_idle_enable "$@" ;;
    disable) cmd_idle_disable ;;
    status)  cmd_idle_status ;;
    run)     cmd_idle_run ;;  # foreground loop — used by enable/systemd
    *)
      print_err "Unknown idle subcommand: $sub"
      echo "  Usage: joidy idle enable [--idle-hibernate-db] | disable | status" >&2
      exit 1
      ;;
  esac
}

# Host directory where dumps are written:
# JOIDY_BACKUP_DIR (env/.env) → $JOIDY_DATA_DIR/backups (same default compose
# uses for the backup service's bind mount).
backup_dir() {
  local d
  d=$(read_setting JOIDY_BACKUP_DIR "")
  [ -z "$d" ] && d="$JOIDY_DATA_DIR/backups"
  echo "$d"
}

pg_ready_or_fail() {
  local pg_user pg_db
  pg_user=$(read_setting POSTGRES_USER joidy)
  pg_db=$(read_setting POSTGRES_DB joidy)
  if ! $DOCKER_CMD $ENV_FILE_ARG exec -T postgres pg_isready -U "$pg_user" -d "$pg_db" >/dev/null 2>&1; then
    print_err "The 'postgres' service is not running — start it first (joidy up or make dev)."
    exit 1
  fi
}

cmd_backup() {
  pg_ready_or_fail
  local pg_user pg_db dir file ts
  pg_user=$(read_setting POSTGRES_USER joidy)
  pg_db=$(read_setting POSTGRES_DB joidy)
  dir=$(backup_dir)
  mkdir -p "$dir"
  ts=$(date +%Y%m%d-%H%M%S)
  file="$dir/joidy-${ts}.dump"
  print_status "Dumping '$pg_db' → $file"
  # Local socket auth inside the postgres container is trust, so no password is
  # needed here. Write to a temp name first: a failed dump never leaves a
  # truncated archive masquerading as a good backup.
  if $DOCKER_CMD $ENV_FILE_ARG exec -T postgres pg_dump -Fc -U "$pg_user" -d "$pg_db" > "$file.tmp"; then
    mv "$file.tmp" "$file"
  else
    rm -f "$file.tmp"
    print_err "pg_dump failed"
    exit 1
  fi
  print_ok "Backup written: $file ($(du -h "$file" | cut -f1))"
  # Apply the same retention policy the scheduled sidecar uses. The script
  # lives next to joidy in repo clones and in <project>/scripts on system
  # installs (e.g. AUR /usr/share/joidy/scripts).
  local prune_script=""
  for candidate in "$SCRIPT_DIR/db_backup.sh" "$PROJECT_DIR/scripts/db_backup.sh"; do
    [ -f "$candidate" ] && prune_script="$candidate" && break
  done
  if [ -n "$prune_script" ]; then
    BACKUP_DIR="$dir" \
    BACKUP_RETENTION_DAYS="$(read_setting BACKUP_RETENTION_DAYS 14)" \
    BACKUP_RETENTION_WEEKS="$(read_setting BACKUP_RETENTION_WEEKS 4)" \
    BACKUP_WEEKLY_DAY="$(read_setting BACKUP_WEEKLY_DAY 0)" \
      bash "$prune_script" prune || print_warn "retention pruning failed"
  fi
}

cmd_restore() {
  local file="" force=0 arg
  for arg in "$@"; do
    case "$arg" in
      --force|-f) force=1 ;;
      *) [ -z "$file" ] && file="$arg" ;;
    esac
  done
  if [ -z "$file" ]; then
    print_err "Usage: joidy restore <file.dump> [--force]"
    exit 1
  fi
  if [ ! -f "$file" ]; then
    print_err "Backup file not found: $file"
    echo "  Dumps live in: $(backup_dir)" >&2
    exit 1
  fi
  if [ "$(head -c 5 "$file" 2>/dev/null)" != "PGDMP" ]; then
    print_err "'$file' is not a pg_dump custom-format archive (missing PGDMP header)"
    exit 1
  fi
  pg_ready_or_fail
  local pg_user pg_db n_tables
  pg_user=$(read_setting POSTGRES_USER joidy)
  pg_db=$(read_setting POSTGRES_DB joidy)
  n_tables=$($DOCKER_CMD $ENV_FILE_ARG exec -T postgres psql -U "$pg_user" -d "$pg_db" -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null || echo "")
  if [ -n "$n_tables" ] && [ "$n_tables" -gt 0 ] && [ "$force" -ne 1 ]; then
    print_err "Database '$pg_db' is live ($n_tables tables) — refusing to overwrite without --force."
    echo "  The restore runs pg_restore --clean, which drops existing objects first."
    echo "  To proceed:  joidy restore $file --force"
    exit 1
  fi
  print_status "Restoring $file → '$pg_db'"
  cat "$file" | $DOCKER_CMD $ENV_FILE_ARG exec -T postgres \
    pg_restore -U "$pg_user" -d "$pg_db" --clean --if-exists --no-owner --no-privileges
  print_ok "Restore complete."
  print_warn "Restart the services so they pick up the restored state: joidy restart"
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
  joidy idle enable [--idle-hibernate-db]
                   Start the background idle watchdog (auto-sleep)
  joidy idle disable
                   Stop the watchdog (running services untouched)
  joidy idle status
                   Watcher state, last activity, time until sleep
  joidy backup     Write a compressed pg_dump to the backups dir
  joidy restore <file> [--force]  Restore a dump into the database
                   (refuses to overwrite a live DB without --force)
  joidy help       Show this help message

Idle watchdog: `joidy idle enable` detaches a watcher that polls established
HTTP connections on the published ports (frontend/api/ai-service/worker),
active PostgreSQL sessions, and vault file changes. After JOIDY_IDLE_TIMEOUT
minutes (.env, default 15) with no activity it snapshots the running services
and sleeps the stack via the existing `joidy sleep` path plus the frontend;
postgres keeps running unless enabled with --idle-hibernate-db. `joidy wake`
— or any new activity — restores the recorded services. An optional systemd
user unit ships in scripts/joidy-idle-watchdog.service.

Scheduled backups: `joidy up` starts the `backup` sidecar automatically —
pg_dump -Fc on BACKUP_SCHEDULE (cron, default "0 3 * * *"), dumps in
<data>/backups (or JOIDY_BACKUP_DIR), pruned to BACKUP_RETENTION_DAYS daily +
BACKUP_RETENTION_WEEKS weekly dumps. Set BACKUP_ENABLED=false to opt out.
Verify backups end-to-end with: make backup-verify

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
  idle)     shift; cmd_idle "$@" ;;
  backup)   cmd_backup ;;
  restore)  shift; cmd_restore "$@" ;;
  help|--help|-h) cmd_help ;;
  *)
    print_err "Unknown command: $1"
    echo ""
    cmd_help
    exit 1
    ;;
esac
