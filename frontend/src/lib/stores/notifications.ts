import { writable } from 'svelte/store';

export interface Notification {
  id: string;
  message: string;
  type: 'info' | 'success' | 'level' | 'error';
}

export const notifications = writable<Notification[]>([]);

// Deduplication map to prevent identical toasts flooding during quick parallel requests
const activeNotifications = new Set<string>();

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
  setTimeout(() => {
    activeNotifications.delete(message);
  }, 3000);

  const id = `notif-${Date.now()}`;
  notifications.update(ns => [...ns, { id, message, type }]);
  setTimeout(() => {
    notifications.update(ns => ns.filter(n => n.id !== id));
  }, 4000);
}

export function dismissNotification(id: string): void {
  notifications.update(ns => ns.filter(n => n.id !== id));
}
