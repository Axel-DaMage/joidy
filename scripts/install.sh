#!/usr/bin/env bash
# Joidy — universal one-shot installer for Linux / macOS / WSL2
#
# Usage (Linux / macOS / WSL2):
#   curl -fsSL https://raw.githubusercontent.com/Axel-DaMage/joidy/development/scripts/install.sh | bash
#
# Windows (PowerShell) — separate installer:
#   irm https://raw.githubusercontent.com/Axel-DaMage/joidy/development/scripts/install.ps1 | iex
#
# Environment overrides:
#   JOIDY_DIR    — install location (default: $HOME/joidy)
#   JOIDY_BRANCH — git branch to clone  (default: development)
set -euo pipefail

REPO="https://github.com/Axel-DaMage/joidy.git"
BRANCH="${JOIDY_BRANCH:-development}"
DIR="${JOIDY_DIR:-$HOME/joidy}"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC} $*"; }
err()   { echo -e "${RED}✗${NC} $*" >&2; }
step()  { echo -e "${BLUE}→${NC} ${BOLD}$*${NC}"; }
banner(){ echo -e "\n${BOLD}$*${NC}"; }

# ── OS detection ──────────────────────────────────────────────────────────────
detect_os() {
  case "$(uname -s)" in
    Linux*)
      if grep -qi microsoft /proc/version 2>/dev/null; then
        echo "wsl"
      else
        echo "linux"
      fi
      ;;
    Darwin*) echo "macos" ;;
    *)       echo "unknown" ;;
  esac
}

OS=$(detect_os)

# ── Windows guard: this script must run inside WSL2 ──────────────────────────
if [ "$OS" = "unknown" ]; then
  err "Unsupported OS. On Windows, use the PowerShell installer:"
  echo ""
  echo "  irm https://raw.githubusercontent.com/Axel-DaMage/joidy/development/scripts/install.ps1 | iex"
  echo ""
  exit 1
fi

banner "=== Joidy Installer ==="
echo "  OS: $OS | Target: $DIR | Branch: $BRANCH"
echo ""

# ── Prerequisites ─────────────────────────────────────────────────────────────
step "Checking prerequisites..."

MISSING=0

if ! command -v git &>/dev/null; then
  err "git is required but not installed."
  case "$OS" in
    linux|wsl) echo "  Install: sudo apt install git   (Debian/Ubuntu)"; echo "           sudo dnf install git   (Fedora/RHEL)" ;;
    macos)     echo "  Install: brew install git   or  xcode-select --install" ;;
  esac
  MISSING=1
fi

if ! command -v docker &>/dev/null; then
  warn "Docker not found. Joidy needs Docker to run."
  case "$OS" in
    wsl)   echo "  → Install Docker Desktop on Windows and enable WSL2 integration:" ; echo "    https://docs.docker.com/desktop/wsl/" ;;
    linux) echo "  → Install: https://docs.docker.com/engine/install/" ;;
    macos) echo "  → Install Docker Desktop: https://docs.docker.com/desktop/mac/install/" ;;
  esac
  warn "Continuing — you can install Docker later before running 'joidy up'."
else
  ok "Docker: $(docker --version | cut -d' ' -f3 | tr -d ',')"
fi

if [ "$MISSING" = "1" ]; then
  err "Please install missing dependencies and re-run the installer."
  exit 1
fi

# ── Clone repo ────────────────────────────────────────────────────────────────
step "Setting up repository at $DIR..."

if [ -d "$DIR/.git" ]; then
  warn "Joidy already installed at $DIR"
  echo "  To update: joidy pull  (or: cd $DIR && git pull && docker compose pull && docker compose up -d)"
else
  git clone --depth 1 --branch "$BRANCH" "$REPO" "$DIR"
  ok "Cloned branch '$BRANCH' into $DIR"
fi

cd "$DIR"

# ── .env bootstrap ────────────────────────────────────────────────────────────
step "Configuring environment..."

if [ ! -f .env ]; then
  cp .env.example .env
  ok "Created .env from .env.example"

  # Auto-generate secrets so first boot works without manual edits
  if command -v openssl &>/dev/null; then
    SECRET_KEY=$(openssl rand -hex 32)
    POSTGRES_PASSWORD=$(openssl rand -hex 24)
    sed -i.bak "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" .env
    sed -i.bak "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|" .env
    rm -f .env.bak
    ok "Auto-generated SECRET_KEY and POSTGRES_PASSWORD"
  else
    warn "openssl not found — edit SECRET_KEY and POSTGRES_PASSWORD in .env before starting"
  fi
else
  ok ".env already exists — keeping your existing configuration"
fi

# ── Install 'joidy' CLI ───────────────────────────────────────────────────────
step "Installing joidy CLI..."

LOCAL_BIN="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/joidy"
JOIDY_SCRIPT="$DIR/scripts/joidy.sh"

mkdir -p "$LOCAL_BIN" "$CONFIG_DIR"

# Persist the project path so the CLI works from any directory
echo "$DIR" > "$CONFIG_DIR/path"
ok "Project path saved to $CONFIG_DIR/path"

# (Re)create symlink — -f replaces any stale previous install
ln -sf "$JOIDY_SCRIPT" "$LOCAL_BIN/joidy"
chmod +x "$JOIDY_SCRIPT"
ok "Installed 'joidy' CLI → $LOCAL_BIN/joidy"

# ── PATH setup ────────────────────────────────────────────────────────────────
ensure_path() {
  local rc_file="$1"
  local marker="# Added by Joidy installer"
  if [ -f "$rc_file" ] && ! grep -q "$marker" "$rc_file"; then
    printf '\n%s\nexport PATH="$HOME/.local/bin:$PATH"\n' "$marker" >> "$rc_file"
    ok "Added ~/.local/bin to PATH in $rc_file"
    return 0
  fi
  return 1
}

PATH_UPDATED=0
case ":$PATH:" in
  *":$LOCAL_BIN:"*)
    ok "~/.local/bin already in PATH" ;;
  *)
    SHELL_NAME="$(basename "${SHELL:-bash}")"
    case "$SHELL_NAME" in
      zsh)  ensure_path "$HOME/.zshrc"  && PATH_UPDATED=1 ;;
      fish) warn "Fish shell detected. Run: fish_add_path ~/.local/bin" ;;
      *)    ensure_path "$HOME/.bashrc" && PATH_UPDATED=1 ;;
    esac
    if [ "$PATH_UPDATED" = "0" ] && [ "$SHELL_NAME" != "fish" ]; then
      warn "Could not auto-update PATH. Add this to your shell rc file:"
      echo '  export PATH="$HOME/.local/bin:$PATH"'
    fi
    ;;
esac

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║   Joidy installed successfully!               ║${NC}"
echo -e "${GREEN}${BOLD}╚═══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}${BOLD}Next steps:${NC}"
echo ""
echo "  1. Set your GEMINI_API_KEY (free at https://aistudio.google.com/):"
echo "       nano $DIR/.env"
echo ""
echo "  2. Set your Obsidian vault path in .env:"
echo "       OBSIDIAN_VAULT_PATH=~/Documents/MyVault"
echo ""
if [ "$PATH_UPDATED" = "1" ]; then
  echo "  3. Reload your shell:"
  echo "       source ~/.${SHELL_NAME}rc"
  echo ""
  echo "  4. Start Joidy:"
else
  echo "  3. Start Joidy:"
fi
echo "       joidy up"
echo ""
echo "  Then open: http://localhost:3000"
echo ""
echo -e "${BLUE}Help:${NC}    joidy help"
echo -e "${BLUE}Logs:${NC}    joidy logs"
echo -e "${BLUE}Stop:${NC}    joidy down"
echo -e "${BLUE}Update:${NC}  joidy pull"
echo ""
if [ "$OS" = "wsl" ]; then
  echo -e "${YELLOW}WSL2 note:${NC} Make sure Docker Desktop → Settings → Resources → WSL Integration"
  echo "  has your distro enabled, then click 'Apply & Restart'."
  echo ""
fi
