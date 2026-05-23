import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';

export function createLocalStorageStore<T>(key: string, initialValue: T) {
  const storedValue = browser ? localStorage.getItem(key) : null;
  const initial = storedValue ? JSON.parse(storedValue) : initialValue;

  const store = writable<T>(initial);

  store.subscribe(value => {
    if (browser) {
      localStorage.setItem(key, JSON.stringify(value));
    }
  });

  return store;
}

export function useLocalStorage<T>(key: string, initialValue: T) {
  return createLocalStorageStore<T>(key, initialValue);
}

export function getLocalStorage<T>(key: string): T | null {
  if (!browser) return null;
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setLocalStorage<T>(key: string, value: T): void {
  if (!browser) return;
  localStorage.setItem(key, JSON.stringify(value));
}

export function removeLocalStorage(key: string): void {
  if (!browser) return;
  localStorage.removeItem(key);
}