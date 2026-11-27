// Alarms, countdown timers and stopwatch state for the /timers page (#969).
//
// Timing model: everything is derived from absolute `Date.now()` timestamps
// (`endsAt`, `startedAt`), advanced by a Web Worker tick that is not throttled
// in backgrounded tabs — countdowns can never drift or freeze when the user
// switches away.
//
// Persistence model (per the issue's refinement):
//  - Alarms: the API (`/user-settings/alarms`, backed by system_config) is the
//    source of truth; localStorage is only a render cache for instant paint.
//  - Timers & stopwatch: sessionStorage — they survive reloads/navigation for
//    the browser session, nothing more.

import { browser } from '$app/env';
import { derived, get, writable } from 'svelte/store';
import { t } from 'svelte-i18n';
import { api } from '$lib/api';
import { logger } from '$lib/utils/logger';
import { applyStats, showXPGain } from './gamification';
import { showNotification } from './notifications';
import {
  fireClockAlert,
  requestNotificationPermission,
  stopTitleFlash,
  type AlarmSoundId,
} from '$lib/utils/clockAlerts';

// ── Types ───────────────────────────────────────────────────────────────────

export interface Alarm {
  id: string;
  hour: number; // 0–23
  minute: number; // 0–59
  label: string;
  /** JS `Date.getDay()` values (0=Sun … 6=Sat). Empty = fire once. */
  days: number[];
  enabled: boolean;
  snoozeMinutes: number;
  sound: AlarmSoundId;
  /** Absolute timestamp while a snooze is pending; cleared when it fires. */
  snoozedUntil?: number;
}

export type TimerStatus = 'running' | 'paused' | 'done';

export interface TimerItem {
  id: string;
  label: string;
  totalMs: number;
  /** Absolute end timestamp while running; null when paused/done. */
  endsAt: number | null;
  /** Remaining ms while paused; kept at 0 once done. */
  remainingMs: number;
  status: TimerStatus;
  /** Optional accent color (css color string) for the card ring (#1663). */
  color?: string;
  /** Linked Joidy goal id — metadata shown on the timer card (#1663). */
  goalId?: number;
  /** Linked Joidy note id — metadata shown on the timer card (#1663). */
  noteId?: number;
  /** Award focus-session XP via `/gamification/pomodoro` on completion (#1663). */
  awardXp?: boolean;
  /** Re-arm automatically after firing — interval-timer behaviour (#1663). */
  repeat?: boolean;
}

/** Optional metadata accepted by `addTimer` (#1663). */
export interface AddTimerOptions {
  color?: string;
  goalId?: number | null;
  noteId?: number | null;
  awardXp?: boolean;
  repeat?: boolean;
}

export interface Lap {
  n: number;
  lapMs: number;
  totalMs: number;
}

export interface StopwatchState {
  running: boolean;
  /** Timestamp when the current running segment started. */
  startedAt: number | null;
  /** Elapsed ms accumulated before the current running segment. */
  baseMs: number;
  laps: Lap[];
}

export interface ClockAlert {
  kind: 'alarm' | 'timer';
  id: string;
  label: string;
  sound: AlarmSoundId;
}

// ── Stores ──────────────────────────────────────────────────────────────────

export const alarms = writable<Alarm[]>([]);
export const timers = writable<TimerItem[]>([]);
export const stopwatch = writable<StopwatchState>({
  running: false,
  startedAt: null,
  baseMs: 0,
  laps: [],
});
/** Latest engine tick — components derive countdowns from this + endsAt. */
export const now = writable<number>(Date.now());
export const activeAlert = writable<ClockAlert | null>(null);

/** Remaining ms for each timer, keyed by id (recomputes on every tick). */
export const timersRemaining = derived([timers, now], ([$timers, $now]) => {
  const map = new Map<string, number>();
  for (const tm of $timers) {
    map.set(
      tm.id,
      tm.status === 'running' && tm.endsAt !== null ? Math.max(0, tm.endsAt - $now) : tm.remainingMs
    );
  }
  return map;
});

/** Elapsed stopwatch ms (recomputes on every tick). */
export const stopwatchElapsed = derived([stopwatch, now], ([$sw, $now]) =>
  $sw.running && $sw.startedAt !== null ? $sw.baseMs + ($now - $sw.startedAt) : $sw.baseMs
);

/** Soonest enabled alarm + its next fire timestamp, or null (#1663 hero card). */
export const nextAlarm = derived([alarms, now], ([$alarms, $now]) => {
  let best: { alarm: Alarm; at: number } | null = null;
  for (const a of $alarms) {
    const at = nextAlarmFireAt(a, $now);
    if (at !== null && (best === null || at < best.at)) best = { alarm: a, at };
  }
  return best;
});

/** Alarms split into upcoming (enabled/snoozed, sorted by next fire) and
 *  inactive (disabled — includes consumed one-shot alarms) (#1663). */
export const alarmGroups = derived([alarms, now], ([$alarms, $now]) => {
  const upcoming: { alarm: Alarm; at: number }[] = [];
  const inactive: Alarm[] = [];
  for (const a of $alarms) {
    const at = nextAlarmFireAt(a, $now);
    if (at !== null) upcoming.push({ alarm: a, at });
    else inactive.push(a);
  }
  upcoming.sort((x, y) => x.at - y.at);
  inactive.sort(
    (x, y) => x.hour * 60 + x.minute - (y.hour * 60 + y.minute)
  );
  return { upcoming, inactive };
});

/** Running countdown timer that finishes first, or null (#1663 hero card). */
export const nextTimer = derived([timers, now], ([$timers, $now]) => {
  let best: { timer: TimerItem; remainingMs: number } | null = null;
  for (const tm of $timers) {
    if (tm.status !== 'running' || tm.endsAt === null) continue;
    const remainingMs = Math.max(0, tm.endsAt - $now);
    if (best === null || remainingMs < best.remainingMs) best = { timer: tm, remainingMs };
  }
  return best;
});

// ── Constants & helpers ─────────────────────────────────────────────────────

const ALARMS_CACHE_KEY = 'joidy-alarms-cache-v1';
const TIMERS_SESSION_KEY = 'joidy-timers-v1';
const STOPWATCH_SESSION_KEY = 'joidy-stopwatch-v1';
const ALARMS_REMOTE_KEY = 'alarms';

/** `${date}T${hour}:${minute}` — identifies a specific minute for an alarm. */
function minuteStamp(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}T${d.getHours()}:${d.getMinutes()}`;
}

function newId(prefix: string): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function tr(key: string, vars?: Record<string, string | number>): string {
  try {
    const out = get(t)(key, vars ? { values: vars } : undefined);
    return typeof out === 'string' && out !== key ? out : key;
  } catch {
    return key;
  }
}

function clampInt(v: unknown, min: number, max: number, fallback: number): number {
  const n = Number(v);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, Math.round(n)));
}

const VALID_SOUNDS: AlarmSoundId[] = ['beep', 'chime', 'pulse'];

/**
 * Next absolute fire timestamp for an alarm, or null when it will never ring.
 * A pending snooze wins over the regular schedule (it fires even if the alarm
 * was disabled meanwhile — mirrors `checkAlarms`). For `days === []` (one-shot)
 * the next occurrence of `hour:minute` is used; for recurring alarms the first
 * matching weekday within the next 8 days.
 */
export function nextAlarmFireAt(a: Alarm, from: number): number | null {
  if (a.snoozedUntil && a.snoozedUntil > from) return a.snoozedUntil;
  if (!a.enabled) return null;
  for (let offset = 0; offset <= 7; offset++) {
    const d = new Date(from);
    d.setDate(d.getDate() + offset);
    d.setHours(a.hour, a.minute, 0, 0);
    const at = d.getTime();
    if (at <= from) continue;
    if (a.days.length === 0) return at;
    if (a.days.includes(d.getDay())) return at;
  }
  return null;
}

function sanitizeAlarm(raw: unknown): Alarm | null {
  if (!raw || typeof raw !== 'object') return null;
  const a = raw as Record<string, unknown>;
  const days = Array.isArray(a.days)
    ? a.days.filter((d): d is number => Number.isInteger(d) && d >= 0 && d <= 6)
    : [];
  return {
    id: typeof a.id === 'string' && a.id ? a.id : newId('al'),
    hour: clampInt(a.hour, 0, 23, 7),
    minute: clampInt(a.minute, 0, 59, 0),
    label: typeof a.label === 'string' ? a.label.slice(0, 80) : '',
    days: [...new Set(days)].sort(),
    enabled: a.enabled !== false,
    snoozeMinutes: clampInt(a.snoozeMinutes, 1, 60, 10),
    sound: VALID_SOUNDS.includes(a.sound as AlarmSoundId) ? (a.sound as AlarmSoundId) : 'beep',
    snoozedUntil:
      typeof a.snoozedUntil === 'number' && a.snoozedUntil > Date.now()
        ? a.snoozedUntil
        : undefined,
  };
}

function sanitizeAlarms(raw: unknown): Alarm[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map(sanitizeAlarm)
    .filter((a): a is Alarm => a !== null)
    .slice(0, 100);
}

// ── Alarm persistence ───────────────────────────────────────────────────────
// Remote (system_config via /user-settings) is the source of truth; the
// localStorage blob is a render cache only.

let persistTimeout: ReturnType<typeof setTimeout> | null = null;

function persistAlarms() {
  const list = get(alarms);
  if (browser) {
    try {
      localStorage.setItem(ALARMS_CACHE_KEY, JSON.stringify(list));
    } catch {
      /* cache write is best-effort */
    }
  }
  if (persistTimeout) clearTimeout(persistTimeout);
  // intentional: debounced module-level write — lives for the session (#1003)
  persistTimeout = setTimeout(() => {
    api.userSettings.set(ALARMS_REMOTE_KEY, list).catch((e: unknown) => {
      logger.warn('[timers] failed to persist alarms to API:', e);
    });
  }, 400);
}

function loadAlarmCache(): Alarm[] {
  if (!browser) return [];
  try {
    const raw = localStorage.getItem(ALARMS_CACHE_KEY);
    return raw ? sanitizeAlarms(JSON.parse(raw)) : [];
  } catch {
    return [];
  }
}

async function loadAlarmsFromApi() {
  try {
    const res = await api.userSettings.get<unknown>(ALARMS_REMOTE_KEY);
    // null = nothing saved remotely yet: keep the render cache instead of
    // wiping it with an empty list.
    if (!Array.isArray(res?.value)) return;
    const remote = sanitizeAlarms(res.value);
    alarms.set(remote);
    if (browser) {
      try {
        localStorage.setItem(ALARMS_CACHE_KEY, JSON.stringify(remote));
      } catch {
        /* ignore */
      }
    }
  } catch (e) {
    // Offline / unauthenticated: keep the render cache already shown.
    logger.warn('[timers] alarm fetch failed, using local cache:', e);
  }
}

// ── Session persistence (timers + stopwatch) ────────────────────────────────

function persistTimersSession() {
  if (!browser) return;
  try {
    sessionStorage.setItem(TIMERS_SESSION_KEY, JSON.stringify(get(timers)));
  } catch {
    /* ignore */
  }
}

function restoreTimersSession() {
  if (!browser) return;
  try {
    const raw = sessionStorage.getItem(TIMERS_SESSION_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return;
    const restored: TimerItem[] = [];
    for (const t of parsed) {
      if (!t || typeof t !== 'object') continue;
      const totalMs = clampInt(t.totalMs, 1, 24 * 60 * 60 * 1000, 0);
      if (!totalMs) continue;
      const restoredTimer: TimerItem = {
        id: typeof t.id === 'string' && t.id ? t.id : newId('tm'),
        label: typeof t.label === 'string' ? t.label.slice(0, 80) : '',
        totalMs,
        endsAt: typeof t.endsAt === 'number' ? t.endsAt : null,
        remainingMs: clampInt(t.remainingMs, 0, 24 * 60 * 60 * 1000, totalMs),
        status:
          t.status === 'running' || t.status === 'paused' || t.status === 'done'
            ? t.status
            : 'paused',
      };
      // #1663 optional metadata — preserved across session restore.
      if (typeof t.color === 'string' && t.color) {
        restoredTimer.color = t.color.slice(0, 32);
      }
      if (Number.isInteger(t.goalId)) restoredTimer.goalId = t.goalId;
      if (Number.isInteger(t.noteId)) restoredTimer.noteId = t.noteId;
      if (t.awardXp === true) restoredTimer.awardXp = true;
      if (t.repeat === true) restoredTimer.repeat = true;
      restored.push(restoredTimer);
    }
    timers.set(restored.slice(0, 50));
  } catch {
    /* corrupt session data — start clean */
  }
}

function persistStopwatchSession() {
  if (!browser) return;
  try {
    sessionStorage.setItem(STOPWATCH_SESSION_KEY, JSON.stringify(get(stopwatch)));
  } catch {
    /* ignore */
  }
}

function restoreStopwatchSession() {
  if (!browser) return;
  try {
    const raw = sessionStorage.getItem(STOPWATCH_SESSION_KEY);
    if (!raw) return;
    const s = JSON.parse(raw);
    if (!s || typeof s !== 'object') return;
    stopwatch.set({
      running: s.running === true,
      startedAt: typeof s.startedAt === 'number' ? s.startedAt : null,
      baseMs: clampInt(s.baseMs, 0, Number.MAX_SAFE_INTEGER, 0),
      laps: Array.isArray(s.laps)
        ? s.laps
            .filter(
              (l: unknown): l is Lap =>
                !!l &&
                typeof l === 'object' &&
                Number.isFinite((l as Lap).lapMs) &&
                Number.isFinite((l as Lap).totalMs)
            )
            .map((l: Lap, i: number) => ({ n: i + 1, lapMs: l.lapMs, totalMs: l.totalMs }))
            .slice(0, 500)
        : [],
    });
  } catch {
    /* ignore */
  }
}

// ── Tick engine (Web Worker + fallback) ─────────────────────────────────────

let engineStarted = false;
let worker: Worker | null = null;
let fallbackInterval: ReturnType<typeof setInterval> | null = null;

/** Alarm ids → minute stamp already fired, so a minute never double-fires. */
const firedStamps = new Map<string, string>();

/**
 * Process one clock tick: refresh `now`, flip finished countdown timers and
 * fire due alarms. Exported so tests can drive ticks deterministically.
 */
export function onTick(tickNow: number) {
  now.set(tickNow);
  checkTimers(tickNow);
  checkAlarms(tickNow);
}

function checkTimers(tickNow: number) {
  const list = get(timers);
  const finished: TimerItem[] = [];
  let changed = false;
  const next = list.map((tm) => {
    if (tm.status === 'running' && tm.endsAt !== null && tm.endsAt <= tickNow) {
      changed = true;
      finished.push(tm);
      if (tm.repeat) {
        // Interval timer (#1663): fire the alert and immediately re-arm from
        // now so a missed boundary never cascades into repeat fires.
        return { ...tm, endsAt: tickNow + tm.totalMs, remainingMs: tm.totalMs };
      }
      return { ...tm, status: 'done' as TimerStatus, endsAt: null, remainingMs: 0 };
    }
    return tm;
  });
  if (!changed) return;
  timers.set(next);
  for (const tm of finished) {
    alertTimerFinished(tm);
    if (tm.awardXp) awardTimerXp(tm);
  }
}

/**
 * Feed a completed focus timer into the gamification engine (#1663). Reuses
 * the `/gamification/pomodoro` event — the backend dedupes on `pomodoro_id`
 * and refuses sessions under its minimum duration, so arbitrary short timers
 * are a safe no-op.
 */
function awardTimerXp(tm: TimerItem) {
  const minutes = Math.round(tm.totalMs / 60_000);
  if (minutes < 1) return;
  try {
    void api.gamification
      .pomodoro({ duration_minutes: minutes, pomodoro_id: `clock-${tm.id}-${Date.now()}` })
      .then((res) => {
        if (res && res.xp_awarded > 0) {
          applyStats(res);
          showXPGain(res.xp_awarded);
        }
      })
      .catch((e: unknown) => {
        logger.warn('[timers] XP award request failed:', e);
      });
  } catch (e) {
    // Gamification client unavailable (e.g. bare test mocks) — non-fatal.
    logger.warn('[timers] XP award unavailable:', e);
  }
}

function checkAlarms(tickNow: number) {
  const d = new Date(tickNow);
  const stamp = minuteStamp(d);
  const day = d.getDay();
  let changed = false;
  const next = get(alarms).map((a) => {
    // A pending snooze fires even if the alarm was toggled off meanwhile
    // (one-shot alarms disable themselves on first fire).
    if (a.snoozedUntil && tickNow >= a.snoozedUntil) {
      changed = true;
      const fired = { ...a, snoozedUntil: undefined };
      alertAlarmFired(fired);
      return fired;
    }
    if (!a.enabled) return a;
    if (d.getHours() !== a.hour || d.getMinutes() !== a.minute) return a;
    if (a.days.length > 0 && !a.days.includes(day)) return a;
    if (firedStamps.get(a.id) === stamp) return a;
    firedStamps.set(a.id, stamp);
    changed = true;
    // One-shot alarms consume themselves when they ring.
    const fired = a.days.length === 0 ? { ...a, enabled: false } : a;
    alertAlarmFired(fired);
    return fired;
  });
  if (changed) {
    alarms.set(next);
    persistAlarms();
  }
}

function alertAlarmFired(a: Alarm) {
  const title = tr('timers.alert.alarmTitle');
  const body = a.label || `${String(a.hour).padStart(2, '0')}:${String(a.minute).padStart(2, '0')}`;
  activeAlert.set({ kind: 'alarm', id: a.id, label: body, sound: a.sound });
  fireClockAlert({ title, body, tag: `joidy-alarm-${a.id}`, sound: a.sound });
}

function alertTimerFinished(tm: TimerItem) {
  const title = tr('timers.alert.timerTitle');
  const body = tm.label || tr('timers.alert.timerDone');
  activeAlert.set({ kind: 'timer', id: tm.id, label: body, sound: 'beep' });
  fireClockAlert({ title, body, tag: `joidy-timer-${tm.id}`, sound: 'beep' });
}

/**
 * Start the ticking engine once per session. Uses a Web Worker so ticks are
 * not throttled when the tab is hidden; falls back to a main-thread interval
 * where Worker is unavailable (older browsers, test environments).
 */
export function initTimersEngine() {
  if (engineStarted || !browser) return;
  engineStarted = true;

  restoreTimersSession();
  restoreStopwatchSession();
  alarms.set(loadAlarmCache());
  void loadAlarmsFromApi();

  const tickNow = () => onTick(Date.now());
  try {
    worker = new Worker(new URL('../workers/timerTick.worker.ts', import.meta.url), {
      type: 'module',
    });
    worker.onmessage = (e: MessageEvent<{ type: string; now: number }>) => {
      if (e.data?.type === 'tick') onTick(e.data.now);
    };
    worker.onerror = (e) => {
      logger.warn('[timers] tick worker failed, falling back to setInterval:', e);
      worker?.terminate();
      worker = null;
      if (!fallbackInterval) {
        // intentional: engine interval lives for the app session (#1003)
        fallbackInterval = setInterval(tickNow, 250);
      }
    };
    worker.postMessage('start');
  } catch (e) {
    logger.warn('[timers] Worker unavailable, falling back to setInterval:', e);
    // intentional: engine interval lives for the app session (#1003)
    fallbackInterval = setInterval(tickNow, 250);
  }

  // Keep session state in sync so a reload resumes running timers.
  timers.subscribe(() => persistTimersSession());
  stopwatch.subscribe(() => persistStopwatchSession());

  // Alarms/timers should be able to notify even when the app is not focused.
  void requestNotificationPermission();
}

// ── Alarm actions ───────────────────────────────────────────────────────────

export function saveAlarm(input: Omit<Alarm, 'id'> & { id?: string }) {
  const alarm = sanitizeAlarm({ ...input, id: input.id ?? newId('al') });
  if (!alarm) return;
  alarms.update((list) => {
    const idx = list.findIndex((a) => a.id === alarm.id);
    if (idx >= 0) {
      const next = [...list];
      next[idx] = alarm;
      return next;
    }
    return [...list, alarm].sort((x, y) => x.hour * 60 + x.minute - (y.hour * 60 + y.minute));
  });
  persistAlarms();
}

export function deleteAlarm(id: string) {
  alarms.update((list) => list.filter((a) => a.id !== id));
  firedStamps.delete(id);
  persistAlarms();
}

export function toggleAlarm(id: string, enabled: boolean) {
  alarms.update((list) =>
    list.map((a) =>
      a.id === id ? { ...a, enabled, snoozedUntil: enabled ? a.snoozedUntil : undefined } : a
    )
  );
  persistAlarms();
}

// ── Alert actions (banner buttons) ─────────────────────────────────────────

export function dismissAlert() {
  const alert = get(activeAlert);
  if (!alert) return;
  activeAlert.set(null);
  stopTitleFlash();
  if (alert.kind === 'alarm') {
    alarms.update((list) =>
      list.map((a) => (a.id === alert.id ? { ...a, snoozedUntil: undefined } : a))
    );
    persistAlarms();
  }
}

export function snoozeAlert() {
  const alert = get(activeAlert);
  if (!alert || alert.kind !== 'alarm') return;
  const alarm = get(alarms).find((a) => a.id === alert.id);
  activeAlert.set(null);
  stopTitleFlash();
  if (!alarm) return;
  const snoozedUntil = Date.now() + Math.max(1, alarm.snoozeMinutes) * 60_000;
  alarms.update((list) => list.map((a) => (a.id === alarm.id ? { ...a, snoozedUntil } : a)));
  persistAlarms();
  showNotification(tr('timers.alert.snoozed', { minutes: alarm.snoozeMinutes }), 'info');
}

// ── Timer actions ───────────────────────────────────────────────────────────

export function addTimer(
  label: string,
  durationMs: number,
  opts: AddTimerOptions = {}
): string | null {
  const totalMs = clampInt(durationMs, 1000, 24 * 60 * 60 * 1000, 0);
  if (!totalMs) return null;
  const id = newId('tm');
  const item: TimerItem = {
    id,
    label: label.slice(0, 80),
    totalMs,
    endsAt: Date.now() + totalMs,
    remainingMs: totalMs,
    status: 'running',
  };
  if (opts.color) item.color = opts.color.slice(0, 32);
  if (Number.isInteger(opts.goalId)) item.goalId = opts.goalId as number;
  if (Number.isInteger(opts.noteId)) item.noteId = opts.noteId as number;
  if (opts.awardXp === true) item.awardXp = true;
  if (opts.repeat === true) item.repeat = true;
  timers.update((list) => [...list, item]);
  return id;
}

export function pauseTimer(id: string) {
  const tickNow = Date.now();
  timers.update((list) =>
    list.map((tm) =>
      tm.id === id && tm.status === 'running' && tm.endsAt !== null
        ? { ...tm, status: 'paused', remainingMs: Math.max(0, tm.endsAt - tickNow), endsAt: null }
        : tm
    )
  );
}

export function resumeTimer(id: string) {
  const tickNow = Date.now();
  timers.update((list) =>
    list.map((tm) =>
      tm.id === id && tm.status === 'paused'
        ? { ...tm, status: 'running', endsAt: tickNow + tm.remainingMs }
        : tm
    )
  );
}

export function resetTimer(id: string) {
  timers.update((list) =>
    list.map((tm) =>
      tm.id === id ? { ...tm, status: 'paused', endsAt: null, remainingMs: tm.totalMs } : tm
    )
  );
}

/** Re-arm a timer to run `totalMs` again from now — used by the "restart"
 *  quick action on done timers and the alert overlay (#1663). */
export function restartTimer(id: string) {
  timers.update((list) =>
    list.map((tm) =>
      tm.id === id
        ? { ...tm, status: 'running', endsAt: Date.now() + tm.totalMs, remainingMs: tm.totalMs }
        : tm
    )
  );
  const alert = get(activeAlert);
  if (alert?.kind === 'timer' && alert.id === id) {
    activeAlert.set(null);
    stopTitleFlash();
  }
}

export function addMinuteToTimer(id: string) {
  const tickNow = Date.now();
  timers.update((list) =>
    list.map((tm) => {
      if (tm.id !== id) return tm;
      if (tm.status === 'running' && tm.endsAt !== null) {
        return { ...tm, endsAt: tm.endsAt + 60_000, totalMs: tm.totalMs + 60_000 };
      }
      if (tm.status === 'done') {
        // Re-arm a finished timer with one minute left.
        return { ...tm, status: 'running', endsAt: tickNow + 60_000, totalMs: tm.totalMs + 60_000 };
      }
      return { ...tm, remainingMs: tm.remainingMs + 60_000, totalMs: tm.totalMs + 60_000 };
    })
  );
}

export function removeTimer(id: string) {
  timers.update((list) => list.filter((tm) => tm.id !== id));
  const alert = get(activeAlert);
  if (alert?.kind === 'timer' && alert.id === id) {
    activeAlert.set(null);
    stopTitleFlash();
  }
}

// ── Stopwatch actions ───────────────────────────────────────────────────────

export function startStopwatch() {
  stopwatch.update((s) => (s.running ? s : { ...s, running: true, startedAt: Date.now() }));
}

export function pauseStopwatch() {
  const tickNow = Date.now();
  stopwatch.update((s) =>
    s.running && s.startedAt !== null
      ? { ...s, running: false, baseMs: s.baseMs + (tickNow - s.startedAt), startedAt: null }
      : s
  );
}

export function lapStopwatch() {
  const tickNow = Date.now();
  stopwatch.update((s) => {
    if (!s.running || s.startedAt === null) return s;
    const total = s.baseMs + (tickNow - s.startedAt);
    const prevTotal = s.laps.length ? s.laps[s.laps.length - 1].totalMs : 0;
    const lapMs = total - prevTotal;
    return { ...s, laps: [...s.laps, { n: s.laps.length + 1, lapMs, totalMs: total }] };
  });
}

export function resetStopwatch() {
  stopwatch.set({ running: false, startedAt: null, baseMs: 0, laps: [] });
}

// ── Formatting helpers (shared by the three panels) ─────────────────────────

export function formatHMS(ms: number): string {
  const totalSec = Math.max(0, Math.ceil(ms / 1000));
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/** `mm:ss.cs` — centisecond precision for the stopwatch display. */
export function formatStopwatch(ms: number): string {
  const cs = Math.floor((Math.max(0, ms) % 1000) / 10);
  const totalSec = Math.floor(Math.max(0, ms) / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  const mm = h > 0 ? `${h}:${String(m).padStart(2, '0')}` : String(m).padStart(2, '0');
  return `${mm}:${String(s).padStart(2, '0')}.${String(cs).padStart(2, '0')}`;
}

/** Compact relative duration — `7h 23m`, `45m`, `12s` — for "next fire"
 *  labels on alarms and the hero countdown (#1663). Sub-minute rounds up so a
 *  due-in-500ms alarm never displays `0s`. */
export function formatDurationShort(ms: number): string {
  const totalSec = Math.max(1, Math.ceil(ms / 1000));
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return m > 0 ? `${h}h ${m}m` : `${h}h`;
  if (m > 0) return `${m}m`;
  return `${s}s`;
}

/** Signed lap-delta — `+2.4s`, `-0.8s`, `±0.0s` — for the stopwatch lap
 *  table's diff column (#1663). */
export function formatSignedDelta(ms: number): string {
  const sec = ms / 1000;
  const abs = Math.abs(sec).toFixed(1);
  if (sec > 0.04) return `+${abs}s`;
  if (sec < -0.04) return `-${abs}s`;
  return `±${abs}s`;
}
