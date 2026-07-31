import { writable } from 'svelte/store';

export interface Notification {
  id: string;
  message: string;
  type: 'info' | 'success' | 'level' | 'error';
}

export const notifications = writable<Notification[]>([]);

// Deduplication map to prevent identical toasts flooding during quick parallel requests
const activeNotifications = new Set<string>();
let dedupTimer: ReturnType<typeof setTimeout> | null = null;
// Track auto-dismiss timers per notification id so they can be cancelled on
// manual dismiss or shutdown (prevents callbacks firing on a stale store and
// avoids accumulating timers across rapid navigation, #413).
const dismissTimers = new Map<string, ReturnType<typeof setTimeout>>();

export function showNotification(
  message: string,
  type: 'info' | 'success' | 'level' | 'error' = 'info'
): void {
  // If this exact notification is already active, ignore it
  if (activeNotifications.has(message)) {
    return;
  }

  activeNotifications.add(message);
  // Allow duplicate alerts only after 3 seconds
  if (dedupTimer) clearTimeout(dedupTimer);
  dedupTimer = setTimeout(() => {
    activeNotifications.delete(message);
    dedupTimer = null;
  }, 3000);

  const id = `notif-${Date.now()}`;
  notifications.update(ns => [...ns, { id, message, type }]);
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
  if (dedupTimer) {
    clearTimeout(dedupTimer);
    dedupTimer = null;
  }
  for (const timer of dismissTimers.values()) clearTimeout(timer);
  dismissTimers.clear();
}
