/**
 * Offline sync store — manages online/offline status, the outbox queue, and
 * background sync of pending changes.
 */
import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';
import { api, type Note } from '$lib/api';
import {
  openDB,
  getAllNotes,
  putNote,
  deleteNote,
  addToOutbox,
  getOutbox,
  removeFromOutbox,
  setMeta,
  getMeta,
  type OutboxChange,
} from '$lib/utils/indexedDB';
import { logger } from '$lib/utils/logger';

export type SyncStatus = 'idle' | 'syncing' | 'error' | 'offline';

export const isOnline = writable(true);
export const pendingChanges = writable(0);
export const syncStatus = writable<SyncStatus>('idle');

const MAX_RETRIES = 5;
let syncTimer: ReturnType<typeof setInterval> | null = null;
let initialized = false;

/** Refreshes the pending change count from the outbox. */
export async function refreshPendingCount(): Promise<void> {
  if (!browser) return;
  try {
    const outbox = await getOutbox();
    pendingChanges.set(outbox.length);
  } catch {
    /* ignore */
  }
}

/**
 * Processes pending changes in the outbox in FIFO order. For each change it
 * calls the appropriate API endpoint and removes the entry on success. On
 * failure the entry's retry count is incremented and retained.
 */
export async function processOutbox(): Promise<void> {
  if (!browser) return;
  if (get(syncStatus) === 'syncing') return;
  if (!navigator.onLine) {
    syncStatus.set('offline');
    return;
  }

  let outbox: OutboxChange[];
  try {
    outbox = await getOutbox();
  } catch (e) {
    logger.error('[offlineSync] Failed to read outbox:', e);
    syncStatus.set('error');
    return;
  }

  if (outbox.length === 0) {
    syncStatus.set('idle');
    pendingChanges.set(0);
    return;
  }

  syncStatus.set('syncing');

  let hadError = false;
  for (const change of outbox) {
    if (change.id === undefined) continue;
    try {
      switch (change.type) {
        case 'create': {
          const result = await api.notes.create({
            title: change.note.title,
            content: change.note.content,
            tags: change.note.tags,
            source_path: change.note.source_path ?? undefined,
          });
          await putNote(result);
          break;
        }
        case 'update': {
          const result = await api.notes.update(change.note.id, {
            title: change.note.title,
            content: change.note.content,
            tags: change.note.tags,
          });
          await putNote(result);
          break;
        }
        case 'delete': {
          await api.notes.delete(change.note.id);
          await deleteNote(change.note.id);
          break;
        }
      }
      await removeFromOutbox(change.id);
    } catch (e) {
      hadError = true;
      logger.warn(`[offlineSync] Failed to process change ${change.id} (${change.type}):`, e);
      const retries = (change.retries ?? 0) + 1;
      if (retries >= MAX_RETRIES) {
        logger.error(`[offlineSync] Dropping change ${change.id} after ${retries} retries`);
        await removeFromOutbox(change.id);
      }
      break;
    }
  }

  await refreshPendingCount();

  if (hadError) {
    syncStatus.set('error');
  } else {
    syncStatus.set('idle');
    await setMeta('lastSyncAt', Date.now());
  }
}

/** Manually triggers outbox processing. */
export async function forceSync(): Promise<void> {
  if (!browser) return;
  if (!navigator.onLine) {
    syncStatus.set('offline');
    return;
  }
  await processOutbox();
}

/**
 * Queues a change in the outbox and updates the IndexedDB cache so the UI
 * reflects the change immediately even while offline.
 */
export async function queueChange(
  type: 'create' | 'update' | 'delete',
  note: Note
): Promise<void> {
  if (!browser) return;
  try {
    await openDB();
    await addToOutbox({ type, note, timestamp: Date.now(), retries: 0 });
    if (type === 'delete') {
      await deleteNote(note.id);
    } else {
      await putNote(note);
    }
    await refreshPendingCount();
    if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({ type: 'joidy:register-sync' });
    }
  } catch (e) {
    logger.error('[offlineSync] Failed to queue change:', e);
  }
}

function startBackgroundSync(): void {
  if (!browser) return;
  if (syncTimer) return;
  syncTimer = setInterval(() => {
    if (navigator.onLine && get(pendingChanges) > 0) {
      processOutbox().catch((e) => logger.error('[offlineSync] background sync failed:', e));
    }
  }, 30_000);
}

function stopBackgroundSync(): void {
  if (syncTimer) {
    clearInterval(syncTimer);
    syncTimer = null;
  }
}

/**
 * Initializes offline sync: sets up online/offline listeners, loads the
 * pending count, and starts the background sync timer. Safe to call once.
 * Returns a cleanup function.
 */
export function initOfflineSync(): () => void {
  if (!browser) return () => {};
  if (initialized) return () => {};
  initialized = true;

  const updateStatus = () => {
    const online = navigator.onLine;
    isOnline.set(online);
    if (online) {
      syncStatus.set('idle');
      processOutbox().catch((e) =>
        logger.error('[offlineSync] post-online sync failed:', e)
      );
    } else {
      syncStatus.set('offline');
    }
  };

  isOnline.set(navigator.onLine);
  if (!navigator.onLine) syncStatus.set('offline');

  refreshPendingCount().catch(() => {});
  startBackgroundSync();

  window.addEventListener('online', updateStatus);
  window.addEventListener('offline', updateStatus);

  const handleSWMessage = (event: MessageEvent) => {
    if (event.data?.type === 'joidy:sync') {
      forceSync().catch((e) => logger.error('[offlineSync] SW-triggered sync failed:', e));
    }
  };
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', handleSWMessage);
  }

  return () => {
    stopBackgroundSync();
    window.removeEventListener('online', updateStatus);
    window.removeEventListener('offline', updateStatus);
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.removeEventListener('message', handleSWMessage);
    }
    initialized = false;
  };
}

export { getAllNotes, putNote, deleteNote, getMeta, setMeta };
