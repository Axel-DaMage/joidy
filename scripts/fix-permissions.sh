#!/bin/bash
# Script to fix Joidy project permissions
# Run this ONCE with: sudo bash scripts/fix-permissions.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "Project root: $PROJECT_ROOT"
cd "$PROJECT_ROOT"

echo "Fixing permissions for Joidy project..."

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

# Fix ownership
echo "Setting ownership to $CURRENT_USER:$CURRENT_GROUP..."
chown -R $CURRENT_USER:$CURRENT_GROUP "$PROJECT_ROOT/frontend/.svelte-kit"
chown -R $CURRENT_USER:$CURRENT_GROUP "$PROJECT_ROOT/frontend/build" 2>/dev/null || true
chown -R $CURRENT_USER:$CURRENT_GROUP "$PROJECT_ROOT/frontend/node_modules/.cache" 2>/dev/null || true
chown -R $CURRENT_USER:$CURRENT_GROUP "$PROJECT_ROOT/api/__pycache__" 2>/dev/null || true

# Set proper permissions
chmod -R 755 "$PROJECT_ROOT/frontend/.svelte-kit"
chmod -R 755 "$PROJECT_ROOT/frontend/build" 2>/dev/null || true

echo "✓ Permissions fixed for user: $CURRENT_USER"
echo "Now run: cd frontend && npm run build"