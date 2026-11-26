import { writable } from 'svelte/store';

/** Sidebar open/close state (used by FocusMode to save/restore sidebar). */
export const uiSidebarOpen = writable(true);
