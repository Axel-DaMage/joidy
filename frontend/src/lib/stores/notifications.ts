import { writable } from 'svelte/store';
import { browser } from '$app/env';
import { SESSION_RESET_EVENT } from './session';

export interface Notification {
  id: string;
  message: string;
  type: 'info' | 'success' | 'level' | 'error';
  /** Optional link target rendered inside the toast (#1200 inbox shortcut). */
  href?: string;
}

export const notifications = writable<Notification[]>([]);

// Deduplication map to prevent identical toasts flooding during quick parallel requests
const activeNotifications = new Set<string>();
// Per-message dedup timers — a shared timer would let a newer notification
// cancel the cleanup of an older message, permanently muting it (#1305).
const dedupTimers = new Map<string, ReturnType<typeof setTimeout>>();
// Track auto-dismiss timers per notification id so they can be cancelled on
// manual dismiss or shutdown (prevents callbacks firing on a stale store and
// avoids accumulating timers across rapid navigation, #413).
const dismissTimers = new Map<string, ReturnType<typeof setTimeout>>();

export function showNotification(
  message: string,
  type: 'info' | 'success' | 'level' | 'error' = 'info',
  href?: string
): void {
  // If this exact notification is already active, ignore it
  if (activeNotifications.has(message)) {
    return;
  }

  activeNotifications.add(message);
  // Allow duplicate alerts only after 3 seconds. Each message owns its timer
  // so firing message B cannot leak message A's dedup entry (#1305).
  // intentional: store-level self-dismissing one-shot; module lifetime,
  // bulk-cleared by clearAllNotificationTimers() (#1003)
  dedupTimers.set(
    message,
    setTimeout(() => {
      activeNotifications.delete(message);
      dedupTimers.delete(message);
    }, 3000)
  );

  const id = `notif-${Date.now()}`;
  notifications.update(ns => [...ns, { id, message, type, href }]);
  // intentional: auto-dismiss one-shot on a module store; tracked in
  // dismissTimers and bulk-cleared by clearAllNotificationTimers() (#1003)
  const timer = setTimeout(() => {
    notifications.update(ns => ns.filter(n => n.id !== id));
    dismissTimers.delete(id);
  }, 4000);
  dismissTimers.set(id, timer);
}

export function dismissNotification(id: string): void {
  const timer = dismissTimers.get(id);
  if (timer) {
    clearTimeout(timer);
    dismissTimers.delete(id);
  }
  notifications.update(ns => ns.filter(n => n.id !== id));
}

/** Cancel all pending notification timers (e.g. on teardown/logout). */
export function clearAllNotificationTimers(): void {
  for (const timer of dedupTimers.values()) clearTimeout(timer);
  dedupTimers.clear();
  // Clearing the timers also drops the only cleanup path for these entries.
  activeNotifications.clear();
  for (const timer of dismissTimers.values()) clearTimeout(timer);
  dismissTimers.clear();
}

// Drop pending toasts on session reset (logout / 401) — messages can embed
// user content (note titles, conflict names) that must not leak to the next
// user on the same browser profile (#1325).
if (browser) {
  window.addEventListener(SESSION_RESET_EVENT, () => {
    clearAllNotificationTimers();
    notifications.set([]);
  });
}
