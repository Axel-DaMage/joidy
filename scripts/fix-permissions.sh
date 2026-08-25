#!/bin/bash
# Clean Docker-generated artifacts and fix project permissions.
#
# No sudo required: since #886 the dev containers run as the host UID/GID, so
# bind-mounted artifacts (.svelte-kit, build, __pycache__, data/logs) are owned
# by the host user and this script can remove them directly.
#
# Backward compatibility: if invoked via sudo (e.g. an old `sudo make
# fix-permissions` muscle memory), it still chowns the tree back to the
# invoking user — useful to clear legacy root-owned files from pre-#886 checkouts.
#
# Usage: bash scripts/fix-permissions.sh   (no sudo needed)

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "Project root: $PROJECT_ROOT"
cd "$PROJECT_ROOT"

# Detect the target user. When run via sudo, prefer the invoking user; otherwise
# use the current (non-root) user.
if [ -n "$SUDO_USER" ] && [ "$(id -u)" -eq 0 ]; then
    CURRENT_USER="$SUDO_USER"
    RUNNING_AS_ROOT=1
else
    CURRENT_USER=$(whoami)
    RUNNING_AS_ROOT=0
fi
CURRENT_GROUP=$(id -gn "$CURRENT_USER" 2>/dev/null || echo "$CURRENT_USER")
CURRENT_UID=$(id -u "$CURRENT_USER" 2>/dev/null || id -u)
CURRENT_GID=$(id -g "$CURRENT_USER" 2>/dev/null || id -g)

echo "Target user: $CURRENT_USER ($CURRENT_UID:$CURRENT_GROUP), running as $([ "$RUNNING_AS_ROOT" = 1 ] && echo root || echo non-root)"

# Remove Python caches (owned by the caller — no sudo needed).
echo "Removing __pycache__ directories..."
find "$PROJECT_ROOT" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
echo "Removing coverage data..."
find "$PROJECT_ROOT" -name ".coverage" -delete 2>/dev/null || true
find "$PROJECT_ROOT" -type d -name ".pytest_cache" -prune -exec rm -rf {} + 2>/dev/null || true

# Remove and recreate .svelte-kit / build (owned by the caller — no sudo needed).
for dir in frontend/.svelte-kit frontend/build; do
    if [ -d "$PROJECT_ROOT/$dir" ]; then
        echo "Removing $dir..."
        if [ -w "$PROJECT_ROOT/$dir" ]; then
            rm -rf "$PROJECT_ROOT/$dir"
        elif [ "$RUNNING_AS_ROOT" = 1 ]; then
            rm -rf "$PROJECT_ROOT/$dir"
        else
            # Legacy root-owned dir from a pre-#886 checkout: a non-root caller
            # cannot delete it. Report and let the one-time sudo path handle it.
            echo "  ⚠ $dir is not writable by $CURRENT_USER (legacy root-owned)."
            ROOT_OWNED=1
        fi
    fi
done

mkdir -p "$PROJECT_ROOT/frontend/.svelte-kit" 2>/dev/null || true

# Fix ownership. As root (sudo) we can chown the whole tree; as a normal user we
# only chown what we own (best-effort) — which is everything in a post-#886 dev
# checkout. chown silently skips files the caller doesn't own.
echo "Setting ownership to $CURRENT_USER:$CURRENT_GROUP..."
for dir in api worker ai-service frontend; do
    [ -d "$PROJECT_ROOT/$dir" ] && chown -R "$CURRENT_USER:$CURRENT_GROUP" "$PROJECT_ROOT/$dir" 2>/dev/null || true
done

chmod -R 755 "$PROJECT_ROOT/frontend/.svelte-kit" 2>/dev/null || true
chmod -R 755 "$PROJECT_ROOT/frontend/build" 2>/dev/null || true

if [ "${ROOT_OWNED:-0}" = 1 ]; then
    echo ""
    echo "⚠ Found legacy root-owned files (from a pre-#886 checkout)."
    echo "  One-time cleanup (run once, then never again):"
    echo "    sudo chown -R \"$CURRENT_UID:$CURRENT_GID\" frontend/.svelte-kit frontend/build"
    echo "  Future 'make dev' runs will not create root-owned files (#886)."
else
    echo "✓ Permissions and artifacts cleaned for user: $CURRENT_USER"
fi
echo "Now run: make dev"
