#!/usr/bin/env bash
# backup_verify.sh — Prove that a pg_dump archive restores cleanly.
#
# Runs against the stack's running `postgres` service (dev or prod):
#   1. pg_dump -Fc the live database into a temp file
#   2. create a throwaway `joidy_test_restore` database and pg_restore into it
#   3. health checks: required schema tables present, alembic_version applied,
#      and an exact per-table row-count comparison vs. the source
#   4. drop the throwaway database
#
# Usage:
#   make backup-verify
#   bash scripts/backup_verify.sh          # same thing
#
# Optional env: COMPOSE_PROJECT_NAME — compose project to exec into
# (Makefile passes -p $(COMPOSE_PROJECT); set this when your stack runs under
# a non-default project name).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

TEST_DB="${BACKUP_VERIFY_DB:-joidy_test_restore}"

# ─── Compose detection (same priority as scripts/joidy.sh) ────────
if command -v docker-compose &>/dev/null; then
  DOCKER_CMD="docker-compose"
elif command -v docker &>/dev/null; then
  DOCKER_CMD="docker compose"
elif command -v podman-compose &>/dev/null; then
  DOCKER_CMD="podman-compose"
elif command -v podman &>/dev/null && podman compose version &>/dev/null 2>&1; then
  DOCKER_CMD="podman compose"
else
  echo "ERROR: neither docker nor podman compose found" >&2
  exit 1
fi

ENV_FILE_ARG=""
ENV_FILE=""
if [ -f "$PROJECT_DIR/.env" ]; then
  ENV_FILE="$PROJECT_DIR/.env"
elif [ -f "$HOME/.config/joidy/.env" ]; then
  ENV_FILE="$HOME/.config/joidy/.env"
  ENV_FILE_ARG="--env-file $ENV_FILE"
fi

read_env() {
  local var="$1" default="$2" val=""
  if [ -n "$ENV_FILE" ]; then
    val=$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d'=' -f2-)
  fi
  echo "${val:-$default}"
}

PGUSER="$(read_env POSTGRES_USER joidy)"
PGDATABASE="$(read_env POSTGRES_DB joidy)"

dc_exec() { $DOCKER_CMD $ENV_FILE_ARG exec -T postgres "$@"; }

if ! dc_exec pg_isready -U "$PGUSER" -d "$PGDATABASE" >/dev/null 2>&1; then
  echo "ERROR: the 'postgres' service is not running (start it with 'joidy up' or 'make dev')" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
  dc_exec psql -U "$PGUSER" -d postgres -qc "DROP DATABASE IF EXISTS ${TEST_DB}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "── joidy backup verification ────────────────────────────"
echo "  source db:   $PGDATABASE"
echo "  restore db:  $TEST_DB (throwaway)"
echo ""

# ─── 1. Dump ──────────────────────────────────────────────────────
echo "[1/4] pg_dump -Fc $PGDATABASE → temp archive"
dc_exec pg_dump -Fc -U "$PGUSER" -d "$PGDATABASE" > "$TMP_DIR/joidy.dump"
if [ "$(head -c 5 "$TMP_DIR/joidy.dump")" != "PGDMP" ]; then
  echo "ERROR: dump is not a valid pg_dump custom-format archive" >&2
  exit 1
fi
echo "      archive: $(du -h "$TMP_DIR/joidy.dump" | cut -f1)"

# ─── 2. Restore into throwaway DB ────────────────────────────────
echo "[2/4] pg_restore → $TEST_DB"
dc_exec psql -U "$PGUSER" -d postgres -qc "DROP DATABASE IF EXISTS ${TEST_DB}"
dc_exec psql -U "$PGUSER" -d postgres -qc "CREATE DATABASE ${TEST_DB}"
dc_exec pg_restore -U "$PGUSER" -d "$TEST_DB" --no-owner --no-privileges < "$TMP_DIR/joidy.dump"

# ─── 3. Health checks ────────────────────────────────────────────
echo "[3/4] health checks on restored database"

# 3a. Migration state: alembic_version must exist and be non-empty.
VERSION=$(dc_exec psql -U "$PGUSER" -d "$TEST_DB" -tAc \
  "SELECT version_num FROM alembic_version" 2>/dev/null | tr -d '[:space:]')
if [ -z "$VERSION" ]; then
  echo "ERROR: alembic_version missing/empty in restored database — migrations did not round-trip" >&2
  exit 1
fi
echo "      alembic_version: $VERSION"

# 3b. Required core tables (same set as api/scripts/verify_db_health.py).
MISSING=$(dc_exec psql -U "$PGUSER" -d "$TEST_DB" -tAc "
  SELECT string_agg(t, ', ') FROM (
    VALUES ('alembic_version'), ('notes'), ('tags'), ('note_tags'),
           ('tag_cooccurrences'), ('embedding_failures')
  ) AS v(t)
  WHERE t NOT IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public')")
if [ -n "${MISSING// /}" ]; then
  echo "ERROR: missing tables in restored database: $MISSING" >&2
  exit 1
fi
echo "      required tables present"

# 3c. Row-count sanity: every public table must have the same row count.
MISMATCHES=0
CHECKED=0
while IFS= read -r table; do
  [ -z "$table" ] && continue
  # </dev/null: `compose exec` forwards stdin and would consume the while-read
  # table list, silently skipping every table after the first.
  SRC=$(dc_exec psql -U "$PGUSER" -d "$PGDATABASE" -tAc "SELECT count(*) FROM \"$table\"" </dev/null)
  DST=$(dc_exec psql -U "$PGUSER" -d "$TEST_DB" -tAc "SELECT count(*) FROM \"$table\"" </dev/null)
  CHECKED=$((CHECKED + 1))
  if [ "$SRC" != "$DST" ]; then
    echo "      MISMATCH: $table source=$SRC restored=$DST"
    MISMATCHES=$((MISMATCHES + 1))
  fi
done < <(dc_exec psql -U "$PGUSER" -d "$TEST_DB" -tAc \
  "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")
if [ "$MISMATCHES" -gt 0 ]; then
  echo "ERROR: $MISMATCHES table(s) have different row counts after restore" >&2
  exit 1
fi
echo "      row counts verified across $CHECKED tables"

# ─── 4. Done (throwaway DB dropped by trap) ───────────────────────
echo "[4/4] dropping $TEST_DB"
echo ""
echo "✓ Backup round-trip verified: dump → restore → health check OK"
