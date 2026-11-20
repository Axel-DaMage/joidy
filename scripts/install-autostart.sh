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

# ── Baseline sandboxing (#1327) ───────────────────────────────────────
# This is a systemd --user unit: the namespace options below implicitly
# enable PrivateUsers= and need unprivileged user namespaces
# (kernel.unprivileged_userns_clone=1 — the default on most distros).
NoNewPrivileges=yes
PrivateTmp=yes
# Mount the whole filesystem read-only except the paths allow-listed in
# ReadWritePaths= (the "-" prefix silently skips paths that don't exist
# instead of failing namespace setup). The CLI writes: the project dir
# (.env + data/, resolved at install time), the XDG data dir (data/idle
# state + backups/), ~/.config/joidy (env file on read-only installs),
# docker/podman client state and rootless podman storage.
ProtectSystem=strict
ReadWritePaths=-${PROJECT_DIR} -${XDG_DATA_HOME:-$HOME/.local/share}/joidy
ReadWritePaths=-%h/joidy -%h/.config/joidy -%h/.local/share/joidy -%h/.docker
ReadWritePaths=-%h/.config/containers -%h/.local/share/containers -%h/.cache/containers
ReadWritePaths=-%t/containers -%t/podman
# Home and /run/user stay READABLE — ~/.config/joidy/path, the .env file
# and the Obsidian vault (OBSIDIAN_VAULT_PATH) are read from there — but
# writable only via the allow-list above.
ProtectHome=read-only
RestrictSUIDSGID=yes
LockPersonality=yes
ProtectKernelModules=yes
# AF_UNIX: engine socket + journal. AF_INET/AF_INET6: API health checks.
# AF_NETLINK: iproute2 (ss, ip, hostname -I) used by the port checks and
# LAN-IP detection in scripts/joidy.sh — without it ss fails
# silently and busy ports would appear free.
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK
# Only bash and the docker/podman clients run — no JIT needs W+X pages.
MemoryDenyWriteExecute=yes

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
