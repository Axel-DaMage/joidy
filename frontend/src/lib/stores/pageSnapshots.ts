import { writable, get } from 'svelte/store';
import { browser } from '$app/env';

interface PageSnapshot {
  path: string;
  timestamp: number;
  state: Record<string, any>;
  scrollPositions: Record<string, number>;
}

const SNAPSHOT_TTL = 10 * 60 * 1000;
const STORAGE_KEY = 'joidy_page_snapshots';

// Snapshots are captured on `beforeunload` — an in-memory store loses them
// on the very reload they were taken for, so they also write through to
// sessionStorage (cleared on logout together with the other session data,
// #1305).
const snapshots = writable<Record<string, PageSnapshot>>(load());

function load(): Record<string, PageSnapshot> {
  if (!browser) return {};
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function persist(): void {
  if (!browser) return;
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(get(snapshots)));
  } catch {
    /* quota / private mode — ignore */
  }
}

export function captureSnapshot(
  path: string,
  state: Record<string, unknown>,
  scrollEls: { id: string; scrollTop: number }[]
): void {
  const scroll: Record<string, number> = {};
  scrollEls.forEach(el => {
    if (el.id) scroll[el.id] = el.scrollTop;
  });
  
  snapshots.update(s => ({
    ...s,
    [path]: { path, timestamp: Date.now(), state, scrollPositions: scroll }
  }));
  persist();
}

export function getSnapshot(path: string): PageSnapshot | null {
  const s = get(snapshots)[path];
  if (!s) return null;
  if (Date.now() - s.timestamp > SNAPSHOT_TTL) return null;
  return s;
}

export function hasSnapshot(path: string): boolean {
  return getSnapshot(path) !== null;
}

export function clearSnapshot(path: string): void {
  snapshots.update(s => {
    const next = { ...s };
    delete next[path];
    return next;
  });
  persist();
}