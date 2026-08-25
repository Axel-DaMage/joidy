#!/usr/bin/env bash
# Joidy — one-shot installer for Linux/macOS.
#
# Clones the repo, copies .env, and installs the `joidy` CLI as a symlink
# in ~/.local/bin so the user can run `joidy up` from anywhere.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Axel-DaMage/joidy/main/scripts/install.sh | bash
#
# Environment overrides:
#   DIR   — install location (default: $HOME/joidy)
#   BRANCH — git branch/revision to clone (default: main)
set -e

REPO="https://github.com/Axel-DaMage/joidy.git"
BRANCH="${BRANCH:-main}"
DIR="${DIR:-$HOME/joidy}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()    { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
err()   { echo -e "${RED}✗${NC} $1" >&2; }
step()  { echo -e "${BLUE}→${NC} $1"; }

# ─── Prerequisites ────────────────────────────────────────────────
if ! command -v git &>/dev/null; then
  err "git is required but not installed."
  exit 1
fi
if ! command -v docker &>/dev/null; then
  warn "Docker is not installed. The CLI will be installed, but you'll need Docker to run Joidy."
  echo "  Install: https://docs.docker.com/engine/install/"
fi

# ─── Clone repo ───────────────────────────────────────────────────
if [ -d "$DIR" ]; then
  warn "Joidy already exists at $DIR"
  echo "  To update: cd $DIR && git pull && docker compose pull && docker compose up -d"
else
  step "Downloading Joidy to $DIR..."
  git clone --depth 1 --branch "$BRANCH" "$REPO" "$DIR"
  ok "Cloned into $DIR"
fi

cd "$DIR"

# ─── .env bootstrap ───────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  ok "Created .env from .env.example"
else
  ok ".env already exists"
fi

# ─── Install `joidy` CLI into ~/.local/bin ────────────────────────
LOCAL_BIN="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/joidy"
JOIDY_SCRIPT="$DIR/scripts/joidy.sh"

mkdir -p "$LOCAL_BIN" "$CONFIG_DIR"

# Persist the project path so the CLI survives renames/moves of the symlink.
echo "$DIR" > "$CONFIG_DIR/path"
ok "Project path saved to $CONFIG_DIR/path"

# (Re)create the symlink. -f overwrites a stale previous install.
ln -sf "$JOIDY_SCRIPT" "$LOCAL_BIN/joidy"
chmod +x "$JOIDY_SCRIPT"
ok "Installed 'joidy' CLI → $LOCAL_BIN/joidy"

# ─── Ensure ~/.local/bin is in PATH ───────────────────────────────
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
    ok "~/.local/bin already in PATH"
    ;;
  *)
    # Detect the user's shell rc file.
    SHELL_NAME="$(basename "${SHELL:-bash}")"
    case "$SHELL_NAME" in
      zsh)  ensure_path "$HOME/.zshrc"  && PATH_UPDATED=1 ;;
      fish) warn "Fish detected. Add ~/.local/bin to fish_user_paths manually:" \
              && echo "  fish_add_path ~/.local/bin" ;;
      *)    ensure_path "$HOME/.bashrc" && PATH_UPDATED=1 ;;
    esac
    if [ "$PATH_UPDATED" = "0" ]; then
      warn "Could not auto-update PATH. Add this to your shell rc:"
      echo '  export PATH="$HOME/.local/bin:$PATH"'
    fi
    ;;
esac

# ─── Done ─────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Joidy installed successfully!               ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Edit $DIR/.env with your credentials:"
echo "     - GEMINI_API_KEY:    get free at https://aistudio.google.com/"
echo "     - OBSIDIAN_VAULT_PATH: path to your Obsidian vault (supports ~, e.g. ~/Documentos/notas/mi-vault)"
echo "     - SECRET_KEY:        run: openssl rand -hex 32"
echo ""
if [ "$PATH_UPDATED" = "1" ]; then
  echo "  2. Reload your shell:"
  echo "       source ~/.${SHELL_NAME}rc"
  echo "  3. Start Joidy:"
else
  echo "  2. Start Joidy:"
fi
echo "       joidy up"
echo ""
echo "  Then open http://localhost:3000"
echo ""
echo -e "${BLUE}Updates:${NC} cd $DIR && git pull && docker compose pull && docker compose up -d"
