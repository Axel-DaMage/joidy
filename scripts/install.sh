#!/usr/bin/env bash
# Joidy — universal one-shot installer for Linux / macOS / WSL2
#
# Usage (Linux / macOS / WSL2):
#   curl -fsSL https://raw.githubusercontent.com/Axel-DaMage/joidy/main/scripts/install.sh | bash
#
# Windows (PowerShell) — separate installer:
#   irm https://raw.githubusercontent.com/Axel-DaMage/joidy/main/scripts/install.ps1 | iex
#
# What it does:
#   1. Checks git and a container engine (Docker/Podman). If the engine is
#      missing or not running it prints the official install link and waits
#      for one user confirmation, then retries once. It never installs Docker
#      itself (#983).
#   2. Clones Axel-DaMage/joidy (branch: $JOIDY_BRANCH, default main) into
#      $JOIDY_DIR (default ~/joidy). An existing checkout is offered a
#      `git pull` update path; a non-repo directory is never overwritten.
#   3. Bootstraps .env from .env.example and auto-generates SECRET_KEY and
#      POSTGRES_PASSWORD.
#   4. Interactively asks for GEMINI_API_KEY and the Obsidian vault path —
#      the only configuration Joidy needs — and writes them to .env.
#   5. Installs the `joidy` CLI into ~/.local/bin and wires PATH.
#   6. Runs `joidy up` when an engine is ready and a terminal is attached,
#      then opens http://localhost:<FRONTEND_PORT> in the default browser.
#
# Environment overrides:
#   JOIDY_DIR            — install location (default: $HOME/joidy)
#   JOIDY_BRANCH         — git branch to clone  (default: main)
#   JOIDY_NONINTERACTIVE — set to 1 to disable all prompts (CI/scripted use)
#   JOIDY_SKIP_START     — set to 1 to skip `joidy up` at the end
set -euo pipefail

REPO="https://github.com/Axel-DaMage/joidy.git"
BRANCH="${JOIDY_BRANCH:-main}"
DIR="${JOIDY_DIR:-$HOME/joidy}"
NONINTERACTIVE="${JOIDY_NONINTERACTIVE:-0}"
SKIP_START="${JOIDY_SKIP_START:-0}"

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

# ── Interactivity ─────────────────────────────────────────────────────────────
# `curl | bash` leaves stdin attached to the pipe, so prompts must be read
# from /dev/tty. CI and scripted runs have no controlling terminal at all —
# detect that once and skip every prompt instead of blocking.
CAN_PROMPT=0
if [ "$NONINTERACTIVE" != "1" ]; then
  if [ -t 0 ] || (exec 3</dev/tty) 2>/dev/null; then
    CAN_PROMPT=1
  fi
fi

# read_tty <prompt> <varname> — reads one line from the user's terminal.
# Only call when CAN_PROMPT=1.
read_tty() {
  local prompt_text="$1" var_name="$2"
  if [ -t 0 ]; then
    read -r -p "$prompt_text" "$var_name" || true
  else
    read -r -p "$prompt_text" "$var_name" </dev/tty || true
  fi
}

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
  echo "  irm https://raw.githubusercontent.com/Axel-DaMage/joidy/main/scripts/install.ps1 | iex"
  echo ""
  exit 1
fi

banner "=== Joidy Installer ==="
echo "  OS: $OS | Target: $DIR | Branch: $BRANCH"
echo ""

# ── Prerequisites ─────────────────────────────────────────────────────────────
step "Checking prerequisites..."

if ! command -v git &>/dev/null; then
  err "git is required but not installed."
  case "$OS" in
    linux|wsl) echo "  Install: sudo apt install git   (Debian/Ubuntu)"; echo "           sudo dnf install git   (Fedora/RHEL)" ;;
    macos)     echo "  Install: brew install git   or  xcode-select --install" ;;
  esac
  err "Please install git and re-run the installer."
  exit 1
fi
GIT_VER="$(git --version 2>/dev/null | awk '{print $3}' || true)"
ok "git: ${GIT_VER:-found}"

# Container engine: Joidy runs on Docker or Podman. The engine must be both
# installed AND running (docker/podman info) before we can start the stack.
engine_ready() {
  if command -v docker &>/dev/null; then
    docker info &>/dev/null && return 0
  fi
  if command -v podman &>/dev/null; then
    podman info &>/dev/null && return 0
  fi
  return 1
}

docker_install_hint() {
  case "$OS" in
    wsl)   echo "  → Install Docker Desktop on Windows and enable WSL2 integration:"
           echo "    https://docs.docker.com/desktop/wsl/" ;;
    linux) echo "  → Install Docker: https://docs.docker.com/engine/install/"
           echo "    (or Podman: https://podman.io/docs/installation)" ;;
    macos) echo "  → Install Docker Desktop: https://docs.docker.com/desktop/install/mac-install/"
           echo "    (or Podman: https://podman.io/docs/installation)" ;;
  esac
}

ENGINE_READY=0
if engine_ready; then
  ENGINE_READY=1
  if command -v docker &>/dev/null && docker info &>/dev/null; then
    ok "Docker: $(docker --version 2>/dev/null | awk '{print $3}' | tr -d ',' || true)"
  else
    ok "Podman: $(podman --version 2>/dev/null | awk '{print $3}' || true)"
  fi
else
  warn "No running container engine found. Joidy needs Docker (or Podman)."
  docker_install_hint
  if [ "$CAN_PROMPT" = "1" ]; then
    # Per #983: print the official link, wait for user confirmation, retry
    # the check exactly once. Docker is never installed automatically.
    read_tty "Press Enter once the engine is installed and running (Ctrl+C to abort)..." _
    if engine_ready; then
      ENGINE_READY=1
      ok "Container engine is ready."
    else
      warn "Engine still not available — continuing without starting services."
      warn "After installing Docker, start Joidy with: joidy up"
    fi
  else
    warn "Continuing — install a container engine, then run 'joidy up'."
  fi
fi

# ── Clone repo ────────────────────────────────────────────────────────────────
step "Setting up repository at $DIR..."

if [ -d "$DIR/.git" ]; then
  warn "Existing Joidy checkout found at $DIR"
  if [ "$CAN_PROMPT" = "1" ]; then
    REPLY=""
    read_tty "Update it now? [Y/n] " REPLY
    case "$REPLY" in
      [nN]*)
        ok "Keeping existing checkout." ;;
      *)
        if git -C "$DIR" pull --ff-only; then
          ok "Updated to latest."
        else
          warn "git pull failed — keeping current checkout."
        fi ;;
    esac
  else
    echo "  To update later: cd $DIR && git pull"
  fi
elif [ -d "$DIR" ] && [ -n "$(ls -A -- "$DIR" 2>/dev/null)" ]; then
  # Never overwrite a directory the installer did not create (#983).
  err "$DIR exists but is not a Joidy git checkout — refusing to overwrite."
  echo "  Move it aside, or install elsewhere:"
  echo "    JOIDY_DIR=/path/to/joidy bash install.sh"
  exit 1
else
  # `--` ends option parsing so a JOIDY_DIR starting with '-' cannot be read
  # as a git flag (#1326).
  git clone --depth 1 --branch "$BRANCH" -- "$REPO" "$DIR"
  ok "Cloned branch '$BRANCH' into $DIR"
fi

cd -- "$DIR"

# ── .env bootstrap ────────────────────────────────────────────────────────────
step "Configuring environment..."

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
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
    warn "openssl not found — 'joidy up' will generate the secrets on first run"
  fi
else
  ok ".env already exists — keeping your existing configuration"
fi

# ── Interactive initial configuration ────────────────────────────────────────
# set_env <KEY> <value> <file> — set or append KEY=value, escaping sed
# metacharacters in the value (& | \) so user input cannot corrupt the file.
set_env() {
  local key="$1" value="$2" file="$3" esc
  esc=$(printf '%s' "$value" | sed -e 's/\([\\&|]\)/\\\1/g')
  if grep -qE "^${key}=" "$file"; then
    sed -i.bak "s|^${key}=.*|${key}=${esc}|" "$file" && rm -f "${file}.bak"
  else
    printf '%s=%s\n' "$key" "$value" >> "$file"
  fi
}

if [ "$CAN_PROMPT" = "1" ]; then
  step "Initial configuration (press Enter to skip — you can edit .env later)"
  echo "  Get a free Gemini API key at: https://aistudio.google.com/"

  GEMINI=""
  read_tty "  GEMINI_API_KEY: " GEMINI
  if [ -n "$GEMINI" ]; then
    set_env GEMINI_API_KEY "$GEMINI" .env
    ok "GEMINI_API_KEY saved to .env"
  fi

  VAULT=""
  read_tty "  Path to your Obsidian vault (e.g. ~/Documents/MyVault): " VAULT
  if [ -n "$VAULT" ]; then
    # Docker needs an absolute host path; keep the raw value in .env (the CLI
    # expands ~ itself) but warn early if the directory does not exist.
    VAULT_CHECK="${VAULT/#\~/$HOME}"
    if [ -d "$VAULT_CHECK" ]; then
      ok "Vault found: $VAULT_CHECK"
    else
      warn "Directory does not exist yet: $VAULT_CHECK (create it before 'joidy up')"
    fi
    set_env OBSIDIAN_VAULT_PATH "$VAULT" .env
    ok "OBSIDIAN_VAULT_PATH saved to .env"
  fi
else
  echo "  Non-interactive run — set these in $DIR/.env before 'joidy up':"
  echo "    GEMINI_API_KEY        (free at https://aistudio.google.com/)"
  echo "    OBSIDIAN_VAULT_PATH   (absolute path to your Obsidian vault)"
fi

# ── Install 'joidy' CLI ───────────────────────────────────────────────────────
step "Installing joidy CLI..."

LOCAL_BIN="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/joidy"
JOIDY_SCRIPT="$DIR/scripts/joidy.sh"

mkdir -p -- "$LOCAL_BIN" "$CONFIG_DIR"

# Persist the project path so the CLI works from any directory
echo "$DIR" > "$CONFIG_DIR/path"
ok "Project path saved to $CONFIG_DIR/path"

# (Re)create symlink — -f replaces any stale previous install
ln -sf -- "$JOIDY_SCRIPT" "$LOCAL_BIN/joidy"
chmod +x -- "$JOIDY_SCRIPT"
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

# ── Start services ────────────────────────────────────────────────────────────
# Auto-start only in interactive runs with a ready engine: first `joidy up`
# pulls several container images, so unattended/CI runs just get instructions.
STARTED=0
if [ "$SKIP_START" = "1" ]; then
  echo "JOIDY_SKIP_START=1 — skipping service start."
elif [ "$ENGINE_READY" = "1" ] && [ "$CAN_PROMPT" = "1" ]; then
  step "Starting Joidy services (first run downloads container images)..."
  if "$JOIDY_SCRIPT" up; then
    STARTED=1
  else
    warn "'joidy up' did not finish cleanly — check 'joidy logs' and retry: joidy up"
  fi
elif [ "$ENGINE_READY" != "1" ]; then
  warn "Container engine not ready — skipping service start."
fi

open_browser() {
  local url="$1"
  (
    case "$OS" in
      macos)
        command -v open &>/dev/null && exec open "$url" ;;
      wsl)
        if command -v wslview &>/dev/null; then exec wslview "$url"
        elif command -v cmd.exe &>/dev/null; then exec cmd.exe /c start "$url"
        fi ;;
      *)
        command -v xdg-open &>/dev/null && exec xdg-open "$url" ;;
    esac
  ) &>/dev/null &
  return 0
}

if [ "$STARTED" = "1" ]; then
  FRONTEND_PORT_OPEN="$(grep -E '^FRONTEND_PORT=' .env 2>/dev/null | head -1 | cut -d'=' -f2- || true)"
  FRONTEND_PORT_OPEN="${FRONTEND_PORT_OPEN:-3000}"
  ok "Joidy is running — opening http://localhost:${FRONTEND_PORT_OPEN} in your browser..."
  open_browser "http://localhost:${FRONTEND_PORT_OPEN}"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║   Joidy installed successfully!               ║${NC}"
echo -e "${GREEN}${BOLD}╚═══════════════════════════════════════════════╝${NC}"
echo ""

if [ "$STARTED" = "1" ]; then
  echo -e "${YELLOW}${BOLD}Joidy is running:${NC}  http://localhost:${FRONTEND_PORT_OPEN}"
  echo ""
  echo "  Manage it with the 'joidy' CLI (restart your shell if it is not found):"
else
  echo -e "${YELLOW}${BOLD}Next steps:${NC}"
  echo ""
  STEP_N=1
  if ! grep -qE '^GEMINI_API_KEY=.' .env 2>/dev/null; then
    echo "  $STEP_N. Set your GEMINI_API_KEY (free at https://aistudio.google.com/):"
    echo "       nano $DIR/.env"
    echo ""
    STEP_N=$((STEP_N + 1))
  fi
  VAULT_CFG="$(grep -E '^OBSIDIAN_VAULT_PATH=' .env 2>/dev/null | head -1 | cut -d'=' -f2- || true)"
  VAULT_DIR="${VAULT_CFG/#\~/$HOME}"
  if [ -z "$VAULT_CFG" ] || [ ! -d "$VAULT_DIR" ]; then
    echo "  $STEP_N. Set your Obsidian vault path in .env:"
    echo "       OBSIDIAN_VAULT_PATH=~/Documents/MyVault"
    echo ""
    STEP_N=$((STEP_N + 1))
  fi
  if [ "$PATH_UPDATED" = "1" ]; then
    echo "  $STEP_N. Reload your shell:"
    echo "       source ~/.${SHELL_NAME}rc"
    echo ""
    STEP_N=$((STEP_N + 1))
  fi
  if [ "$ENGINE_READY" != "1" ]; then
    echo "  $STEP_N. Install a container engine:"
    docker_install_hint
    echo ""
    STEP_N=$((STEP_N + 1))
  fi
  echo "  $STEP_N. Start Joidy:"
  echo "       joidy up"
fi
echo ""
echo -e "${BLUE}Help:${NC}    joidy help"
echo -e "${BLUE}Logs:${NC}    joidy logs"
echo -e "${BLUE}Stop:${NC}    joidy down"
echo -e "${BLUE}Update:${NC}  cd $DIR && git pull"
echo ""
if [ "$OS" = "wsl" ]; then
  echo -e "${YELLOW}WSL2 note:${NC} Make sure Docker Desktop → Settings → Resources → WSL Integration"
  echo "  has your distro enabled, then click 'Apply & Restart'."
  echo ""
fi
