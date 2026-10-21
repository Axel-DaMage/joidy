#!/usr/bin/env bash
# db_backup_loop.sh — Long-running scheduler for the `backup` compose service.
#
# Evaluates BACKUP_SCHEDULE (a 5-field cron expression) once a minute and runs
# db_backup.sh when the current time matches. Runs until stopped.
#
# Environment:
#   BACKUP_SCHEDULE   Cron expression "M H DOM MON DOW" or one of
#                     @hourly, @daily, @midnight, @weekly, @monthly, @yearly.
#                     Field syntax: * , */n , a , a-b , a-b/n , comma lists.
#                     Standard cron rule: when both DOM and DOW are restricted,
#                     either matching triggers a run. Day-of-week 0 or 7 = Sunday.
#                     Default: "0 3 * * *" (daily at 03:00, container TZ).
#   BACKUP_ON_START   If "true", run one backup immediately at startup.
#   TZ                Timezone used for schedule evaluation.
#
# All remaining variables are passed through to db_backup.sh.

set -euo pipefail
# Cron fields contain `*` — this script never relies on pathname expansion, so
# disable globbing entirely to keep `*` literal when fields are word-split.
set -f

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_SCRIPT="$SCRIPT_DIR/db_backup.sh"
BACKUP_SCHEDULE="${BACKUP_SCHEDULE:-0 3 * * *}"
BACKUP_ON_START="${BACKUP_ON_START:-false}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] db_backup_loop: $*"; }
err() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] db_backup_loop ERROR: $*" >&2; }

# ─── Schedule normalization & validation ─────────────────────────
case "$BACKUP_SCHEDULE" in
  "@hourly")              BACKUP_SCHEDULE="0 * * * *" ;;
  "@daily"|"@midnight")   BACKUP_SCHEDULE="0 0 * * *" ;;
  "@weekly")              BACKUP_SCHEDULE="0 0 * * 0" ;;
  "@monthly")             BACKUP_SCHEDULE="0 0 1 * *" ;;
  "@yearly"|"@annually")  BACKUP_SCHEDULE="0 0 1 1 *" ;;
esac

read -r F_MIN F_HOUR F_DOM F_MON F_DOW EXTRA <<< "$BACKUP_SCHEDULE"
if [ -z "${F_DOW:-}" ] || [ -n "${EXTRA:-}" ]; then
  err "invalid BACKUP_SCHEDULE '$BACKUP_SCHEDULE' — expected 5 cron fields"
  exit 1
fi
for f in "$F_MIN" "$F_HOUR" "$F_DOM" "$F_MON" "$F_DOW"; do
  case "$f" in
    *[!0-9*,/-]*) err "invalid cron field '$f' in BACKUP_SCHEDULE"; exit 1 ;;
  esac
done

# ─── Cron field matching ─────────────────────────────────────────
# $1 = field spec, $2 = numeric value → true if the value matches the spec.
field_matches() {
  local field="$1" val="$2" part step lo hi
  local IFS=','
  for part in $field; do
    step=1
    case "$part" in
      */*) step="${part##*/}"; part="${part%%/*}" ;;
    esac
    [ "$step" -gt 0 ] 2>/dev/null || continue
    if [ "$part" = "*" ]; then
      [ $((val % step)) -eq 0 ] && return 0
    elif [[ "$part" == *-* ]]; then
      lo="${part%%-*}"; hi="${part##*-}"
      if [ "$val" -ge "$lo" ] && [ "$val" -le "$hi" ] && [ $(((val - lo) % step)) -eq 0 ]; then
        return 0
      fi
    else
      [ "$val" -eq "$part" ] && return 0
    fi
  done
  return 1
}

# $1 = current day of week (0-6). 7 is an accepted alias for Sunday (0).
dow_matches() {
  local cdow="$1"
  field_matches "$F_DOW" "$cdow" && return 0
  [ "$cdow" -eq 0 ] && field_matches "$F_DOW" 7
}

should_run_now() {
  local cmin chour cdom cmon cdow
  read -r cmin chour cdom cmon cdow <<< "$(date '+%M %H %d %m %w')"
  cmin=$((10#$cmin)); chour=$((10#$chour)); cdom=$((10#$cdom)); cmon=$((10#$cmon)); cdow=$((10#$cdow))
  field_matches "$F_MIN"  "$cmin"  || return 1
  field_matches "$F_HOUR" "$chour" || return 1
  field_matches "$F_MON"  "$cmon"  || return 1
  # Cron rule: DOM and DOW are OR-ed when both are restricted.
  if [ "$F_DOM" != "*" ] && [ "$F_DOW" != "*" ]; then
    field_matches "$F_DOM" "$cdom" || dow_matches "$cdow"
    return
  fi
  field_matches "$F_DOM" "$cdom" || return 1
  dow_matches "$cdow"
}

sleep_interruptible() {
  # `sleep` as a foreground child would delay TERM until it finishes; run it in
  # the background so `wait` is interrupted and the trap fires immediately.
  sleep "$1" &
  wait $! 2>/dev/null || true
}

trap 'log "shutting down"; exit 0' TERM INT

log "scheduler started (BACKUP_SCHEDULE='$BACKUP_SCHEDULE', TZ=${TZ:-UTC})"

if [ "$BACKUP_ON_START" = "true" ]; then
  log "BACKUP_ON_START=true — running an immediate backup"
  bash "$BACKUP_SCRIPT" run || err "startup backup failed"
fi

last_minute=""
while :; do
  current_minute=$(date '+%Y-%m-%d %H:%M')
  if [ "$current_minute" != "$last_minute" ] && should_run_now; then
    last_minute="$current_minute"
    log "schedule matched — starting backup"
    if bash "$BACKUP_SCRIPT" run; then
      log "backup finished"
    else
      err "backup failed (see output above); will retry on next schedule match"
    fi
  fi
  # Sleep until just past the next minute boundary.
  secs=$(date +%S)
  secs=$((10#$secs))
  nap=$((60 - secs))
  [ "$nap" -le 0 ] && nap=60
  sleep_interruptible "$nap"
done
