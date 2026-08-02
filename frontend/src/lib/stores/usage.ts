/**
 * Usage tracking store — records lightweight internal usage events (#250).
 *
 * Tracking only happens while the web app is in the FOREGROUND. We listen to
 * `visibilitychange` and pause tracking when the tab is hidden, resuming when
 * it becomes visible again. Calls are debounced to avoid flooding the backend.
 */
import { browser } from '$app/environment';
import { api } from '$lib/api';
import { logger } from '$lib/utils/logger';

export const EVENT_PAGE_VIEW = 'page_view';
export const EVENT_FEATURE_USE = 'feature_use';
export const EVENT_SESSION_START = 'session_start';
export const EVENT_SESSION_END = 'session_end';

// Minimum interval between tracked events of the same kind (debounce), in ms.
const DEBOUNCE_MS = 2000;
// Page-view debounce is shorter but still avoids duplicate rapid nav events.
const PAGE_VIEW_DEBOUNCE_MS = 800;

let lastTracked: Record<string, number> = {};
let trackingEnabled = true;
let sessionStarted = false;
let initialized = false;

function isForeground(): boolean {
  return typeof document === 'undefined' || document.visibilityState === 'visible';
}

function shouldTrack(eventType: string, debounceMs: number): boolean {
  if (!browser || !trackingEnabled || !isForeground()) return false;
  const now = Date.now();
  const last = lastTracked[eventType] ?? 0;
  if (now - last < debounceMs) return false;
  lastTracked[eventType] = now;
  return true;
}

function send(eventType: string, eventData?: Record<string, unknown>): void {
  if (!browser || !trackingEnabled || !isForeground()) return;
  api.analytics.track(eventType, eventData).catch((e) => logger.debug('[usage] track failed:', e));
}

/** Track a page navigation. Debounced per-path to avoid duplicates. */
export function trackPageView(path: string): void {
  if (!shouldTrack(`page_view:${path}`, PAGE_VIEW_DEBOUNCE_MS)) return;
  send(EVENT_PAGE_VIEW, { path });
}

/** Track usage of a named feature (e.g. "search", "semantic-search"). */
export function trackFeatureUse(feature: string): void {
  if (!shouldTrack(`feature_use:${feature}`, DEBOUNCE_MS)) return;
  send(EVENT_FEATURE_USE, { feature });
}

/** Record the start of an active session (called on app mount / foreground). */
export function trackSessionStart(): void {
  if (!browser || sessionStarted) return;
  if (!shouldTrack(EVENT_SESSION_START, DEBOUNCE_MS)) return;
  sessionStarted = true;
  send(EVENT_SESSION_START);
}

/** Record the end of an active session (called on unmount / backgrounding). */
export function trackSessionEnd(): void {
  if (!browser || !sessionStarted) return;
  sessionStarted = false;
  // Session end is not debounced by lastTracked (we reset sessionStarted),
  // but still respect the foreground gate.
  if (!trackingEnabled || !isForeground()) return;
  send(EVENT_SESSION_END);
}

/**
 * Initialize foreground/background tracking. Call once from the root layout.
 * Returns a cleanup function that removes listeners.
 */
export function initUsageTracking(): (() => void) | null {
  if (!browser || initialized) return null;
  initialized = true;

  const handleVisibility = () => {
    if (document.visibilityState === 'visible') {
      // Resumed foreground — start a new session.
      trackingEnabled = true;
      trackSessionStart();
    } else {
      // Backgrounded — end the current session and pause tracking (#250).
      trackSessionEnd();
      trackingEnabled = false;
    }
  };

  // `pagehide` fires on tab close / navigation away — best-effort session end.
  const handlePageHide = () => {
    trackSessionEnd();
  };

  document.addEventListener('visibilitychange', handleVisibility);
  window.addEventListener('pagehide', handlePageHide);

  return () => {
    document.removeEventListener('visibilitychange', handleVisibility);
    window.removeEventListener('pagehide', handlePageHide);
    initialized = false;
  };
}
