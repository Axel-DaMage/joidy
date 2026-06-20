import { writable, get } from 'svelte/store';

interface PageSnapshot {
  path: string;
  timestamp: number;
  state: Record<string, any>;
  scrollPositions: Record<string, number>;
}

const SNAPSHOT_TTL = 10 * 60 * 1000;

const snapshots = writable<Record<string, PageSnapshot>>({});

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
}