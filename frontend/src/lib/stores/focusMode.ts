import { writable, get, derived } from 'svelte/store';
import { logger } from '$lib/utils/logger';
import {
  phase, running, secondsLeft, pomodorosDone, totalSec,
  workMins, breakMins, startTimer, stopTimer, resetTimer,
} from './pomodoro';
import { showNotification, showXPGain, pingActivity } from './gamification';
import { uiSidebarOpen } from './ui';

export interface FocusModeConfig {
  duration: number;
  breakDuration: number;
  cyclesBeforeLongBreak: number;
  allowedNotifications: string[];
}

export interface FocusSession {
  startTime: number | null;
  duration: number;
  noteId: string | null;
  xpEarned: number;
}

export interface QueuedNotification {
  id: string;
  message: string;
  type: 'info' | 'success' | 'level' | 'error';
  queuedAt: number;
}

const DEFAULT_CONFIG: FocusModeConfig = {
  duration: 25,
  breakDuration: 5,
  cyclesBeforeLongBreak: 4,
  allowedNotifications: [],
};

const STORAGE_KEY = 'joidy-focus-mode-config';

export const isActive = writable(false);
export const config = writable<FocusModeConfig>(DEFAULT_CONFIG);
export const queuedNotifications = writable<QueuedNotification[]>([]);
export const focusSession = writable<FocusSession>({
  startTime: null,
  duration: DEFAULT_CONFIG.duration,
  noteId: null,
  xpEarned: 0,
});

export const elapsedSeconds = derived(
  [focusSession, isActive],
  ([$session, $active]) => {
    if (!$active || $session.startTime === null) return 0;
    return Math.floor((Date.now() - $session.startTime) / 1000);
  }
);

function clampInt(value: unknown, min: number, max: number, fallback: number): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, Math.round(n)));
}

function loadConfig(): FocusModeConfig {
  if (typeof localStorage === 'undefined') return DEFAULT_CONFIG;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_CONFIG;
    const parsed = JSON.parse(raw) as Partial<FocusModeConfig>;
    return {
      duration: clampInt(parsed.duration, 1, 180, DEFAULT_CONFIG.duration),
      breakDuration: clampInt(parsed.breakDuration, 1, 120, DEFAULT_CONFIG.breakDuration),
      cyclesBeforeLongBreak: clampInt(parsed.cyclesBeforeLongBreak, 1, 20, DEFAULT_CONFIG.cyclesBeforeLongBreak),
      allowedNotifications: Array.isArray(parsed.allowedNotifications)
        ? parsed.allowedNotifications.filter((n) => typeof n === 'string')
        : [],
    };
  } catch {
    return DEFAULT_CONFIG;
  }
}

function persistConfig() {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(get(config)));
  } catch {
    // Ignore storage failures
  }
}

export function initFocusModeConfig() {
  config.set(loadConfig());
}

export function updateConfig(patch: Partial<FocusModeConfig>) {
  config.update((c) => {
    const next = { ...c, ...patch };
    if (patch.duration !== undefined) next.duration = clampInt(patch.duration, 1, 180, c.duration);
    if (patch.breakDuration !== undefined) next.breakDuration = clampInt(patch.breakDuration, 1, 120, c.breakDuration);
    if (patch.cyclesBeforeLongBreak !== undefined) {
      next.cyclesBeforeLongBreak = clampInt(patch.cyclesBeforeLongBreak, 1, 20, c.cyclesBeforeLongBreak);
    }
    return next;
  });
  persistConfig();
}

config.subscribe(() => {
  if (typeof localStorage !== 'undefined') {
    persistConfig();
  }
});

function isNotificationAllowed(message: string, type: string): boolean {
  const cfg = get(config);
  if (cfg.allowedNotifications.length === 0) return false;
  return cfg.allowedNotifications.some(
    (allowed) =>
      allowed.toLowerCase() === type.toLowerCase() ||
      message.toLowerCase().includes(allowed.toLowerCase())
  );
}

export function queueNotificationIfActive(
  message: string,
  type: QueuedNotification['type'] = 'info'
) {
  if (!get(isActive)) {
    showNotification(message, type);
    return;
  }
  if (isNotificationAllowed(message, type)) {
    showNotification(message, type);
    return;
  }
  const id = `fq-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  queuedNotifications.update((q) => [...q, { id, message, type, queuedAt: Date.now() }]);
}

function deliverQueuedNotifications() {
  const queued = get(queuedNotifications);
  if (queued.length === 0) return;
  logger.info(`[focusMode] Delivering ${queued.length} queued notification(s)`);
  for (const n of queued) {
    setTimeout(() => showNotification(n.message, n.type), 100);
  }
  queuedNotifications.set([]);
}

export function dismissQueuedNotification(id: string) {
  queuedNotifications.update((q) => q.filter((n) => n.id !== id));
}

let savedSidebarState: boolean | null = null;

function activateZenMode() {
  savedSidebarState = get(uiSidebarOpen);
  uiSidebarOpen.set(false);
}

function deactivateZenMode() {
  if (savedSidebarState !== null) {
    uiSidebarOpen.set(savedSidebarState);
    savedSidebarState = null;
  }
}

export function startFocusMode(noteId?: string) {
  const cfg = get(config);
  workMins.set(cfg.duration);
  breakMins.set(cfg.breakDuration);
  resetTimer();
  phase.set('work');
  secondsLeft.set(cfg.duration * 60);
  pomodorosDone.set(0);
  activateZenMode();
  focusSession.set({
    startTime: Date.now(),
    duration: cfg.duration,
    noteId: noteId ?? null,
    xpEarned: 0,
  });
  queuedNotifications.set([]);
  startTimer();
  isActive.set(true);
  logger.info(
    `[focusMode] Started focus session (${cfg.duration} min)${noteId ? ` for note ${noteId}` : ''}`
  );
}

export function stopFocusMode() {
  if (!get(isActive)) return;
  const session = get(focusSession);
  const wasRunning = get(running);
  stopTimer();
  let xpEarned = 0;
  if (session.startTime !== null) {
    const elapsedMin = Math.max(1, Math.round((Date.now() - session.startTime) / 60000));
    xpEarned = Math.min(elapsedMin, session.duration);
    if (wasRunning && xpEarned < 5) xpEarned = 5;
  }
  pingActivity().catch((e) => logger.error('[focusMode] pingActivity failed:', e));
  if (xpEarned > 0) {
    showXPGain(xpEarned);
  }
  focusSession.update((s) => ({ ...s, xpEarned }));
  deactivateZenMode();
  deliverQueuedNotifications();
  isActive.set(false);
  logger.info(`[focusMode] Stopped focus session. XP earned: ${xpEarned}`);
}
