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

# Services that are stopped during hibernation
HIBERNATE_SERVICES="ai-service worker"

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

cmd_up() {
  print_status "Starting Joidy services..."
  docker compose up -d
  print_status "Waiting for services to stabilize..."
  sleep 5
  cmd_status
  print_access_url
}

cmd_down() {
  print_status "Stopping all Joidy services..."
  docker compose down
  print_ok "All services stopped."
}

cmd_sleep() {
  print_status "Hibernating heavy services (ai-service, worker)..."
  for svc in $HIBERNATE_SERVICES; do
    # Check if the service is running by looking at docker compose ps output
    if docker compose ps "$svc" 2>/dev/null | grep -q "$svc"; then
      docker compose stop "$svc"
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
  for svc in $HIBERNATE_SERVICES; do
    # Check if the service is NOT running (use -a to include stopped containers)
    if docker compose ps -a "$svc" 2>/dev/null | grep -q "$svc"; then
      if docker compose ps "$svc" 2>/dev/null | grep -q "$svc"; then
        print_warn "$svc is already running"
      else
        docker compose start "$svc"
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
  docker compose restart
  print_ok "All services restarted."
  print_access_url
}

cmd_status() {
  print_status "Joidy service status:"
  echo ""
  docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || docker compose ps
}

cmd_logs() {
  local svc="${1:-}"
  if [ -n "$svc" ]; then
    docker compose logs -f "$svc"
  else
    docker compose logs -f
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
