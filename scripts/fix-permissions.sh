#!/bin/bash
# Script to fix Joidy project permissions
# Run this ONCE with: sudo bash scripts/fix-permissions.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "Project root: $PROJECT_ROOT"
cd "$PROJECT_ROOT"

echo "Fixing permissions and cleaning Docker-generated artifacts for Joidy..."

# Detect original user (not root)
if [ -n "$SUDO_USER" ]; then
    CURRENT_USER="$SUDO_USER"
else
    CURRENT_USER=$(whoami)
fi

# If running as root, try to get the actual user
if [ "$CURRENT_USER" = "root" ]; then
    # Try to get the owner of a file in the project
    CURRENT_USER=$(stat -c '%U' "$PROJECT_ROOT/frontend/package.json" 2>/dev/null) || CURRENT_USER="d4mag3"
fi

CURRENT_GROUP=$(id -gn "$CURRENT_USER" 2>/dev/null || echo "d4mag3")

echo "Target user: $CURRENT_USER, group: $CURRENT_GROUP"

# Remove Python caches that may have been generated as root by Docker containers
echo "Removing __pycache__ directories..."
find "$PROJECT_ROOT" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true

# Remove coverage data files
echo "Removing coverage data..."
find "$PROJECT_ROOT" -name ".coverage" -delete 2>/dev/null || true
find "$PROJECT_ROOT" -type d -name ".pytest_cache" -prune -exec rm -rf {} + 2>/dev/null || true

# Remove and recreate .svelte-kit directory with correct ownership
if [ -d "$PROJECT_ROOT/frontend/.svelte-kit" ]; then
    echo "Removing and recreating .svelte-kit..."
    rm -rf "$PROJECT_ROOT/frontend/.svelte-kit"
fi

# Remove build directory
if [ -d "$PROJECT_ROOT/frontend/build" ]; then
    echo "Removing build directory..."
    rm -rf "$PROJECT_ROOT/frontend/build"
fi

# Create fresh directories
mkdir -p "$PROJECT_ROOT/frontend/.svelte-kit"

# Fix ownership of project Python/Node directories that may have root-owned files
echo "Setting ownership to $CURRENT_USER:$CURRENT_GROUP..."
for dir in api worker ai-service frontend; do
    if [ -d "$PROJECT_ROOT/$dir" ]; then
        chown -R $CURRENT_USER:$CURRENT_GROUP "$PROJECT_ROOT/$dir" 2>/dev/null || true
    fi
done

# Set proper permissions for SvelteKit generated directory
chmod -R 755 "$PROJECT_ROOT/frontend/.svelte-kit" 2>/dev/null || true
chmod -R 755 "$PROJECT_ROOT/frontend/build" 2>/dev/null || true

echo "✓ Permissions and artifacts cleaned for user: $CURRENT_USER"
echo "Now run: make dev"