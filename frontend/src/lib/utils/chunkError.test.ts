import { describe, it, expect, vi } from 'vitest';
import {
  CHUNK_RELOAD_KEY,
  CHUNK_RELOAD_COOLDOWN_MS,
  chunkUpdateAvailable,
  isChunkLoadError,
  shouldAttemptReload,
  handleChunkError,
  type StorageLike,
} from './chunkError';
import { get } from 'svelte/store';

function fakeStorage(initial: Record<string, string> = {}): StorageLike & {
  data: Map<string, string>;
} {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
  };
}

describe('isChunkLoadError', () => {
  it('detects Chrome "dynamically imported module" TypeErrors', () => {
    expect(
      isChunkLoadError(
        new TypeError("Failed to fetch dynamically imported module: https://x/_app/immutable/a.js")
      )
    ).toBe(true);
  });

  it('detects Firefox "error loading dynamically imported module"', () => {
    expect(isChunkLoadError(new TypeError('error loading dynamically imported module'))).toBe(true);
  });

  it('detects Safari "Importing a module script failed"', () => {
    expect(
      isChunkLoadError(new TypeError('Importing a module script failed.'))
    ).toBe(true);
  });

  it('detects Vite dev "Outdated Optimize Dep"', () => {
    expect(isChunkLoadError(new Error('504 Outdated Optimize Dep'))).toBe(true);
  });

  it('rejects unrelated errors and non-error values', () => {
    expect(isChunkLoadError(new TypeError('Cannot read properties of undefined'))).toBe(false);
    expect(isChunkLoadError(new Error('Network request failed'))).toBe(false);
    expect(isChunkLoadError('dynamically imported module')).toBe(false);
    expect(isChunkLoadError(null)).toBe(false);
    expect(isChunkLoadError(undefined)).toBe(false);
  });
});

describe('shouldAttemptReload', () => {
  it('allows a reload when no timestamp is stored', () => {
    expect(shouldAttemptReload(fakeStorage(), 1000)).toBe(true);
  });

  it('allows a reload when the stored timestamp is stale', () => {
    const storage = fakeStorage({ [CHUNK_RELOAD_KEY]: '1000' });
    expect(shouldAttemptReload(storage, 1000 + CHUNK_RELOAD_COOLDOWN_MS + 1)).toBe(true);
  });

  it('blocks a reload inside the cooldown window', () => {
    const storage = fakeStorage({ [CHUNK_RELOAD_KEY]: '1000' });
    expect(shouldAttemptReload(storage, 1000 + CHUNK_RELOAD_COOLDOWN_MS)).toBe(false);
    expect(shouldAttemptReload(storage, 1000 + 5_000)).toBe(false);
  });

  it('treats a corrupted timestamp as no timestamp', () => {
    const storage = fakeStorage({ [CHUNK_RELOAD_KEY]: 'not-a-number' });
    expect(shouldAttemptReload(storage, 1000)).toBe(true);
  });
});

describe('handleChunkError', () => {
  it('reloads once and stamps the guard', () => {
    const storage = fakeStorage();
    const reload = vi.fn();
    const result = handleChunkError({ storage, reload, now: 42_000 });
    expect(result).toBe('reloaded');
    expect(reload).toHaveBeenCalledOnce();
    expect(storage.data.get(CHUNK_RELOAD_KEY)).toBe('42000');
  });

  it('prompts instead of reloading inside the cooldown', () => {
    const storage = fakeStorage({ [CHUNK_RELOAD_KEY]: '40000' });
    const reload = vi.fn();
    const result = handleChunkError({ storage, reload, now: 41_000 });
    expect(result).toBe('prompt');
    expect(reload).not.toHaveBeenCalled();
    expect(get(chunkUpdateAvailable)).toBe(true);
    chunkUpdateAvailable.set(false);
  });

  it('prompts when no storage is available', () => {
    const reload = vi.fn();
    const result = handleChunkError({ storage: null, reload, now: 42_000 });
    expect(result).toBe('prompt');
    expect(reload).not.toHaveBeenCalled();
    expect(get(chunkUpdateAvailable)).toBe(true);
    chunkUpdateAvailable.set(false);
  });
});
