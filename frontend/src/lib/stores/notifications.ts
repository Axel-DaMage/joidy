import { writable } from 'svelte/store';

export interface Notification {
  id: string;
  message: string;
  type: 'info' | 'success' | 'level' | 'error';
}

export const notifications = writable<Notification[]>([]);

export function showNotification(
  message: string,
  type: 'info' | 'success' | 'level' | 'error' = 'info'
): void {
  const id = `notif-${Date.now()}`;
  notifications.update(ns => [...ns, { id, message, type }]);
  setTimeout(() => {
    notifications.update(ns => ns.filter(n => n.id !== id));
  }, 4000);
}

export function dismissNotification(id: string): void {
  notifications.update(ns => ns.filter(n => n.id !== id));
}
