import { writable } from 'svelte/store';

export type ToastType = 'info' | 'success' | 'warning' | 'error';

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
}

export interface ModalState {
  isOpen: boolean;
  component: string | null;
  props: Record<string, any>;
}

export const uiToasts = writable<Toast[]>([]);

let toastId = 0;
// Track auto-dismiss timers per toast id so they can be cancelled on manual
// dismiss or teardown, preventing callbacks firing on a stale store and
// avoiding timer accumulation across rapid navigation (#413).
const toastTimers = new Map<string, ReturnType<typeof setTimeout>>();

export function showToast(message: string, type: ToastType = 'info', duration = 4000) {
  const id = `toast-${++toastId}`;
  uiToasts.update(toasts => [...toasts, { id, message, type, duration }]);
  const timer = setTimeout(() => {
    uiToasts.update(toasts => toasts.filter(t => t.id !== id));
    toastTimers.delete(id);
  }, duration);
  toastTimers.set(id, timer);
}

export function dismissToast(id: string) {
  const timer = toastTimers.get(id);
  if (timer) {
    clearTimeout(timer);
    toastTimers.delete(id);
  }
  uiToasts.update(toasts => toasts.filter(t => t.id !== id));
}

/** Cancel all pending toast timers (e.g. on teardown/logout). */
export function clearAllToastTimers(): void {
  for (const timer of toastTimers.values()) clearTimeout(timer);
  toastTimers.clear();
}

export const uiModal = writable<ModalState>({
  isOpen: false,
  component: null,
  props: {},
});

export function openModal(component: string, props: Record<string, any> = {}) {
  uiModal.set({ isOpen: true, component, props });
}

export function closeModal() {
  uiModal.set({ isOpen: false, component: null, props: {} });
}

export const uiSidebarOpen = writable(true);

export function toggleSidebar() {
  uiSidebarOpen.update(v => !v);
}

export const uiTheme = writable<'dark' | 'light'>('dark');

export function setTheme(theme: 'dark' | 'light') {
  uiTheme.set(theme);
}