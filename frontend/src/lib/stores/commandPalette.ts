import { writable } from 'svelte/store';

/** Whether the command palette modal is currently open. */
export const isOpen = writable<boolean>(false);

/** Open the command palette. */
export function open() {
  isOpen.set(true);
}

/** Close the command palette. */
export function close() {
  isOpen.set(false);
}

/** Toggle the command palette open/closed. */
export function toggle() {
  isOpen.update((v) => !v);
}
