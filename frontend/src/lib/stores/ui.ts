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

export function showToast(message: string, type: ToastType = 'info', duration = 4000) {
  const id = `toast-${++toastId}`;
  uiToasts.update(toasts => [...toasts, { id, message, type, duration }]);
  setTimeout(() => {
    uiToasts.update(toasts => toasts.filter(t => t.id !== id));
  }, duration);
}

export function dismissToast(id: string) {
  uiToasts.update(toasts => toasts.filter(t => t.id !== id));
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