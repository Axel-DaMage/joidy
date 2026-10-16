#!/usr/bin/env bash
# db_backup.sh — Create a compressed PostgreSQL dump and prune old backups.
#
# Usage:
#   db_backup.sh [run]    Take a dump, then prune per the retention policy.
#   db_backup.sh prune    Prune only (no dump). Safe to run on the host too —
#                         pruning works purely on filenames/timestamps.
#
# Environment:
#   PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE
#       Standard libpq connection variables (run mode only).
#   BACKUP_DIR
#       Directory for dumps. Default: /backups
#   BACKUP_RETENTION_DAYS
#       Keep every dump newer than this many days. Default: 14
#   BACKUP_RETENTION_WEEKS
#       Additionally keep the dump taken on BACKUP_WEEKLY_DAY for this many
#       weeks. Default: 4
#   BACKUP_WEEKLY_DAY
#       Day of week kept as the weekly dump (0=Sunday … 6=Saturday). Default: 0
#
# Dumps are named joidy-YYYYMMDD-HHMMSS.dump (pg_dump custom format, -Fc) and
# are written atomically (temp file + rename) so a failed dump never leaves a
# truncated archive in place.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
BACKUP_RETENTION_WEEKS="${BACKUP_RETENTION_WEEKS:-4}"
BACKUP_WEEKLY_DAY="${BACKUP_WEEKLY_DAY:-0}"

PGHOST="${PGHOST:-postgres}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-joidy}"
PGDATABASE="${PGDATABASE:-joidy}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] db_backup: $*"; }
err() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] db_backup ERROR: $*" >&2; }

# ─── Portable date helpers (GNU date and BSD/macOS date) ─────────
# $1 = "YYYYMMDD-HHMMSS" → epoch seconds
to_epoch() {
  local stamp="$1" d t
  d="${stamp%%-*}"
  t="${stamp##*-}"
  date -d "${d:0:4}-${d:4:2}-${d:6:2} ${t:0:2}:${t:2:2}:${t:4:2}" +%s 2>/dev/null \
    || date -j -f "%Y%m%d-%H%M%S" "$stamp" +%s
}

# $1 = epoch seconds → day of week (0=Sunday)
dow_of() {
  date -d "@$1" +%w 2>/dev/null || date -j -r "$1" +%w
}

# ─── Retention pruning ────────────────────────────────────────────
# Keep: every dump younger than BACKUP_RETENTION_DAYS, plus dumps taken on
# BACKUP_WEEKLY_DAY younger than BACKUP_RETENTION_WEEKS * 7 days.
# Files whose timestamps can't be parsed are never deleted.
prune_backups() {
  local now daily_sec weekly_sec f name stamp epoch age dow pruned=0
  now=$(date +%s)
  daily_sec=$((BACKUP_RETENTION_DAYS * 86400))
  weekly_sec=$((BACKUP_RETENTION_WEEKS * 7 * 86400))

  for f in "$BACKUP_DIR"/joidy-*.dump; do
    [ -e "$f" ] || continue
    name="${f##*/}"
    stamp="${name#joidy-}"
    stamp="${stamp%.dump}"
    # Skip files that don't match the expected timestamp shape.
    case "$stamp" in
      [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]) ;;
      *) continue ;;
    esac
    epoch=$(to_epoch "$stamp") || { log "keeping unparseable dump: $name"; continue; }
    age=$((now - epoch))
    [ "$age" -le "$daily_sec" ] && continue
    dow=$(dow_of "$epoch")
    if [ "$dow" = "$BACKUP_WEEKLY_DAY" ] && [ "$age" -le "$weekly_sec" ]; then
      continue
    fi
    rm -f "$f"
    log "pruned $name (age $((age / 86400))d)"
    pruned=$((pruned + 1))
  done
  [ "$pruned" -gt 0 ] && log "pruned $pruned old dump(s)"
  return 0
}

# ─── Dump ─────────────────────────────────────────────────────────
run_backup() {
  if [ -z "${PGPASSWORD:-}" ]; then
    err "PGPASSWORD is required"
    exit 1
  fi
  export PGPASSWORD
  mkdir -p "$BACKUP_DIR"
  local ts name tmp
  ts=$(date +%Y%m%d-%H%M%S)
  name="joidy-${ts}.dump"
  tmp="$BACKUP_DIR/.${name}.tmp"
  trap 'rm -f "$tmp"' EXIT
  log "dumping ${PGDATABASE}@${PGHOST}:${PGPORT} → $BACKUP_DIR/$name"
  pg_dump -Fc -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -f "$tmp"
  mv "$tmp" "$BACKUP_DIR/$name"
  trap - EXIT
  log "backup complete: $name ($(du -h "$BACKUP_DIR/$name" | cut -f1))"
}

case "${1:-run}" in
  run)   run_backup; prune_backups ;;
  prune) prune_backups ;;
  -h|--help|help)
    sed -n '2,30p' "$0"
    ;;
  *)
    err "unknown subcommand: $1 (expected run|prune)"
    exit 1
    ;;
esac
