/**
 * IndexedDB wrapper for offline note caching and outbox queue.
 *
 * Database: "joidy"
 * Stores:
 *   - "notes":  keyPath "id" — cached notes for offline read access
 *   - "outbox": keyPath "id" — pending changes awaiting sync (autoIncrement id)
 *   - "meta":   keyPath "key" — metadata such as lastSyncAt
 */
import { browser } from '$app/environment';
import type { Note } from '$lib/api';

const DB_NAME = 'joidy';
const DB_VERSION = 1;
const NOTES_STORE = 'notes';
const OUTBOX_STORE = 'outbox';
const META_STORE = 'meta';

/** A pending change queued in the outbox for later sync. */
export interface OutboxChange {
  id?: number;
  type: 'create' | 'update' | 'delete';
  note: Note;
  timestamp: number;
  retries: number;
}

let dbPromise: Promise<IDBDatabase> | null = null;

/** Opens (and upgrades if needed) the "joidy" IndexedDB database. */
export function openDB(): Promise<IDBDatabase> {
  if (!browser) {
    return Promise.reject(new Error('IndexedDB is not available outside the browser'));
  }
  if (dbPromise) return dbPromise;

  dbPromise = new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(NOTES_STORE)) {
        db.createObjectStore(NOTES_STORE, { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains(OUTBOX_STORE)) {
        db.createObjectStore(OUTBOX_STORE, { keyPath: 'id', autoIncrement: true });
      }
      if (!db.objectStoreNames.contains(META_STORE)) {
        db.createObjectStore(META_STORE, { keyPath: 'key' });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error('IndexedDB open blocked'));
  });

  return dbPromise;
}

/** Retrieves all cached notes from IndexedDB, sorted by updated_at desc. */
export async function getAllNotes(): Promise<Note[]> {
  if (!browser) return [];
  try {
    const db = await openDB();
    return await new Promise<Note[]>((resolve, reject) => {
      const tx = db.transaction(NOTES_STORE, 'readonly');
      const store = tx.objectStore(NOTES_STORE);
      const req = store.getAll();
      req.onsuccess = () => {
        const notes = (req.result as Note[]) ?? [];
        notes.sort(
          (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        );
        resolve(notes);
      };
      req.onerror = () => reject(req.error);
    });
  } catch {
    return [];
  }
}

/** Stores or updates a note in the IndexedDB cache. */
export async function putNote(note: Note): Promise<void> {
  if (!browser) return;
  try {
    const db = await openDB();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(NOTES_STORE, 'readwrite');
      tx.objectStore(NOTES_STORE).put(note);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    /* ignore cache write failures */
  }
}

/** Removes a note from the IndexedDB cache. */
export async function deleteNote(id: number): Promise<void> {
  if (!browser) return;
  try {
    const db = await openDB();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(NOTES_STORE, 'readwrite');
      tx.objectStore(NOTES_STORE).delete(id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    /* ignore cache delete failures */
  }
}

/** Adds a pending change to the outbox store. */
export async function addToOutbox(change: Omit<OutboxChange, 'id'>): Promise<number> {
  if (!browser) return -1;
  const db = await openDB();
  return await new Promise<number>((resolve, reject) => {
    const tx = db.transaction(OUTBOX_STORE, 'readwrite');
    const req = tx.objectStore(OUTBOX_STORE).add({ ...change, retries: change.retries ?? 0 });
    req.onsuccess = () => resolve(req.result as number);
    req.onerror = () => reject(req.error);
  });
}

/** Retrieves all pending changes from the outbox in FIFO order. */
export async function getOutbox(): Promise<OutboxChange[]> {
  if (!browser) return [];
  try {
    const db = await openDB();
    return await new Promise<OutboxChange[]>((resolve, reject) => {
      const tx = db.transaction(OUTBOX_STORE, 'readonly');
      const req = tx.objectStore(OUTBOX_STORE).getAll();
      req.onsuccess = () => {
        const items = (req.result as OutboxChange[]) ?? [];
        items.sort((a, b) => a.timestamp - b.timestamp);
        resolve(items);
      };
      req.onerror = () => reject(req.error);
    });
  } catch {
    return [];
  }
}

/** Removes a processed change from the outbox. */
export async function removeFromOutbox(id: number): Promise<void> {
  if (!browser) return;
  try {
    const db = await openDB();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(OUTBOX_STORE, 'readwrite');
      tx.objectStore(OUTBOX_STORE).delete(id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    /* ignore */
  }
}

/** Sets a metadata value (e.g. lastSyncAt). */
export async function setMeta(key: string, value: unknown): Promise<void> {
  if (!browser) return;
  try {
    const db = await openDB();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(META_STORE, 'readwrite');
      tx.objectStore(META_STORE).put({ key, value });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    /* ignore */
  }
}

/** Gets a metadata value by key. */
export async function getMeta<T = unknown>(key: string): Promise<T | null> {
  if (!browser) return null;
  try {
    const db = await openDB();
    return await new Promise<T | null>((resolve, reject) => {
      const tx = db.transaction(META_STORE, 'readonly');
      const req = tx.objectStore(META_STORE).get(key);
      req.onsuccess = () => {
        const result = req.result as { key: string; value: T } | undefined;
        resolve(result ? result.value : null);
      };
      req.onerror = () => reject(req.error);
    });
  } catch {
    return null;
  }
}
