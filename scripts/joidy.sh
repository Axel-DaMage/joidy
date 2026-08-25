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

cmd_up() {
  print_status "Starting Joidy services..."
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
  joidy logs       Tail logs (all services)
  joidy logs api   Tail logs for a specific service
  joidy help       Show this help message

On first run, .env is auto-created from .env.example with generated
POSTGRES_PASSWORD, SECRET_KEY, and GRAFANA_ADMIN_PASSWORD.
For AUR installs (read-only /usr/share/joidy), .env is stored in
~/.config/joidy/.env. Edit it to add GEMINI_API_KEY, OBSIDIAN_VAULT_PATH, etc.

The project directory is auto-detected from the script location.
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
  logs)     cmd_logs "${2:-}" ;;
  help|--help|-h) cmd_help ;;
  *)
    print_err "Unknown command: $1"
    echo ""
    cmd_help
    exit 1
    ;;
esac
