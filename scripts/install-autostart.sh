#!/usr/bin/env bash
# install-autostart.sh — Set up systemd user service for Joidy auto-start on Linux.
#
# Usage:
#   bash scripts/install-autostart.sh          # Install auto-start
#   bash scripts/install-autostart.sh --remove # Remove auto-start

set -e

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_NAME="joidy"
SERVICE_FILE="$HOME/.config/systemd/user/${SERVICE_NAME}.service"

if [ "$1" = "--remove" ]; then
  echo "Removing Joidy auto-start service..."
  systemctl --user stop "${SERVICE_NAME}.service" 2>/dev/null || true
  systemctl --user disable "${SERVICE_NAME}.service" 2>/dev/null || true
  rm -f "$SERVICE_FILE"
  systemctl --user daemon-reload
  echo "✓ Joidy auto-start removed."
  exit 0
fi

echo "Setting up Joidy auto-start via systemd user service..."

# Create systemd user directory if it doesn't exist
mkdir -p "$HOME/.config/systemd/user"

# Write the service file
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Joidy — Personal Growth Dashboard
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PROJECT_DIR}/scripts/joidy_startup.sh
RemainAfterExit=yes
ExecStop=${PROJECT_DIR}/scripts/joidy.sh down

[Install]
WantedBy=default.target
EOF

# Reload systemd and enable the service
systemctl --user daemon-reload
systemctl --user enable "${SERVICE_NAME}.service"

echo ""
echo "✓ Joidy auto-start service installed."
echo ""
echo "The service will start automatically when you log in."
echo ""
echo "Manual commands:"
echo "  systemctl --user start joidy    # Start now"
echo "  systemctl --user stop joidy     # Stop now"
echo "  systemctl --user status joidy   # Check status"
echo "  systemctl --user disable joidy  # Disable auto-start"
echo ""
echo "To remove auto-start: bash scripts/install-autostart.sh --remove"
