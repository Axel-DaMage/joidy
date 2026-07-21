#!/usr/bin/env bash
set -e
REPO="https://github.com/Axel-DaMage/joidy.git"
DIR="${DIR:-$HOME/joidy}"

if [ -d "$DIR" ]; then
  echo "Joidy already exists at $DIR"
  echo "To update: cd $DIR && git pull && docker compose pull && docker compose up -d"
  exit 1
fi

echo "Downloading Joidy to $DIR..."
git clone --depth 1 "$REPO" "$DIR"
cd "$DIR"
cp .env.example .env
echo ""
echo "Done!"
echo ""
echo "Next steps:"
echo "  1. Edit $DIR/.env with your credentials"
echo "  2. Run: cd $DIR && docker compose up -d"
echo "  3. Open http://localhost:3000"
echo ""
echo "For updates: cd $DIR && git pull && docker compose pull && docker compose up -d"