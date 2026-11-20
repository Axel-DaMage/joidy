// Chunk-load failure recovery (#1459).
//
// A new deploy replaces the hashed bundles under `_app/immutable` while
// already-open tabs still reference the old filenames, so every lazy
// `import()` 404s with a TypeError ("Failed to fetch dynamically imported
// module"). Left alone that produces infinite loaders everywhere. This
// module detects those failures and performs a single guarded
// `location.reload()` — the sessionStorage timestamp caps auto-reloads at
// one per cooldown window so a persistently broken deploy can't loop. Once
// the guard is exhausted, `chunkUpdateAvailable` drives a manual
// "new version available — reload" banner rendered by the root layout.

import { writable } from 'svelte/store';
import { logger } from './logger';

export const CHUNK_RELOAD_KEY = 'joidy:chunk-reload-at';
export const CHUNK_RELOAD_COOLDOWN_MS = 2 * 60 * 1000;

// true once a chunk failed and the guarded auto-reload was already spent —
// the layout shows a manual reload banner instead of looping (#1459).
export const chunkUpdateAvailable = writable(false);

export type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;

/**
 * True when `err` looks like a failed dynamic `import()` — a stale/changed
 * chunk the in-page code can only recover from via reload. Covers Chrome
 * ("Failed to fetch dynamically imported module"), Firefox ("error loading
 * dynamically imported module"), Safari ("Importing a module script
 * failed") and the Vite dev-server variant ("Outdated Optimize Dep").
 */
export function isChunkLoadError(err: unknown): boolean {
  if (err == null || typeof err !== 'object') return false;
  const msg = String((err as Error).message ?? '');
  return (
    msg.includes('dynamically imported module') ||
    msg.includes('Importing a module script failed') ||
    msg.includes('Failed to load module script') ||
    msg.includes('Outdated Optimize Dep')
  );
}

/**
 * One auto-reload per cooldown window — the timestamp survives the reload
 * itself, which is what prevents a broken deploy from looping forever.
 */
export function shouldAttemptReload(storage: StorageLike, now: number = Date.now()): boolean {
  const raw = storage.getItem(CHUNK_RELOAD_KEY);
  const last = raw ? Number(raw) : NaN;
  return !Number.isFinite(last) || now - last > CHUNK_RELOAD_COOLDOWN_MS;
}

function safeSessionStorage(): StorageLike | null {
  try {
    return typeof sessionStorage !== 'undefined' ? sessionStorage : null;
  } catch {
    return null;
  }
}

/**
 * React to a detected chunk failure: reload once, then fall back to the
 * manual-update banner. Returns what happened — 'reloaded' | 'prompt'.
 */
export function handleChunkError(opts?: {
  storage?: StorageLike | null;
  reload?: () => void;
  now?: number;
}): 'reloaded' | 'prompt' {
  const storage = opts?.storage !== undefined ? opts.storage : safeSessionStorage();
  const reload = opts?.reload ?? (() => window.location.reload());
  const now = opts?.now ?? Date.now();

  if (storage && shouldAttemptReload(storage, now)) {
    try {
      storage.setItem(CHUNK_RELOAD_KEY, String(now));
    } catch (e) {
      logger.warn('[chunkError] could not persist reload guard:', e);
    }
    reload();
    return 'reloaded';
  }
  logger.error('[chunkError] chunk load failed and auto-reload was already spent — prompting user');
  chunkUpdateAvailable.set(true);
  return 'prompt';
}

/**
 * App-level listeners (#1459): Vite emits `vite:preloadError` when a
 * preloaded dynamic import fails, and any lazy import without its own
 * `.catch` surfaces as an `unhandledrejection` TypeError. Returns the
 * cleanup function.
 */
export function initChunkErrorRecovery(): () => void {
  const onPreloadError = (event: Event) => {
    // Keep Vite from rethrowing the payload as an unhandled rejection.
    event.preventDefault();
    handleChunkError();
  };
  const onUnhandledRejection = (event: PromiseRejectionEvent) => {
    if (isChunkLoadError(event.reason)) {
      event.preventDefault();
      handleChunkError();
    }
  };
  window.addEventListener('vite:preloadError', onPreloadError);
  window.addEventListener('unhandledrejection', onUnhandledRejection);
  return () => {
    window.removeEventListener('vite:preloadError', onPreloadError);
    window.removeEventListener('unhandledrejection', onUnhandledRejection);
  };
}
