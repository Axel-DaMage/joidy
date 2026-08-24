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
fi

# Services that are stopped during hibernation
HIBERNATE_SERVICES="ai-service worker"

# Detect container engine
if command -v docker-compose &>/dev/null; then
  DOCKER_CMD="docker-compose"
elif command -v docker &>/dev/null; then
  DOCKER_CMD="docker compose"
elif command -v podman-compose &>/dev/null; then
  DOCKER_CMD="podman-compose"
elif command -v podman &>/dev/null; then
  DOCKER_CMD="podman compose"
else
  echo -e "${RED}✗ Error: Neither docker nor podman was found in PATH.${NC}" >&2
  exit 1
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
