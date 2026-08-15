import { writable, get, derived } from 'svelte/store';
import { browser } from '$app/environment';
import { api, type Note, type AISuggestion } from '$lib/api';
import { applyGamificationResult } from './gamification';
import { logger } from '$lib/utils/logger';
import {
  isOnline as offlineIsOnline,
  queueChange,
  getAllNotes,
  putNote,
  deleteNote as idbDeleteNote,
} from './offlineSync';

export const notes        = writable<Note[]>([]);
export const currentNote  = writable<Note | null>(null);
export const aiSuggestions = writable<AISuggestion[]>([]);
export const notesLoading  = writable(false);
export const notesLoadedOnce = writable(false);
export const selectedNoteIds = writable<Set<number>>(new Set());
export const bulkMode = writable(false);
export const hasMoreNotes = writable(false);
export const loadingMore = writable(false);

let notesLoaded = false;
let lastTag: string | undefined = undefined;
let pendingLoad = false;
let cacheLoadDone = false;

/** Page size for paginated note fetching. */
const NOTES_PAGE_SIZE = 200;

const CACHE_KEY = 'joidy_notes_cache';

function saveNotesCache(data: Note[]) {
  if (!browser) return;
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify({ data, ts: Date.now() }));
  } catch {}
}

function loadNotesCache(): Note[] | null {
  if (!browser) return null;
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const cached = JSON.parse(raw);
    if (!cached.data || !Array.isArray(cached.data)) return null;
    if (Date.now() - cached.ts > 300000) return null;
    return cached.data;
  } catch {
    return null;
  }
}

export async function loadNotes(tag?: string, force = false): Promise<void> {
  if (pendingLoad) return;
  if (!force && notesLoaded && get(notes).length > 0 && lastTag === tag) return;
  
  if (!force && !cacheLoadDone) {
    const cached = loadNotesCache();
    if (cached && cached.length > 0) {
      notes.set(cached);
      notesLoaded = true;
      cacheLoadDone = true;
    }
  }
  
  pendingLoad = true;
  notesLoading.set(get(notes).length === 0);
  lastTag = tag;

  try {
    const data = await api.notes.list(tag, NOTES_PAGE_SIZE, 0);
    notes.set(data);
    hasMoreNotes.set(data.length >= NOTES_PAGE_SIZE);
    saveNotesCache(data);
    notesLoaded = true;
    cacheLoadDone = true;
    notesLoadedOnce.set(true);
    // Persist fetched notes into IndexedDB for offline access.
    if (browser) {
      Promise.all(data.map((n) => putNote(n))).catch(() => {});
    }
  } catch (e) {
    logger.error('[notes] Failed to load:', e);
    // Fallback to IndexedDB cache when the API is unreachable.
    if (browser) {
      try {
        const cached = await getAllNotes();
        if (cached.length > 0) {
          notes.set(cached);
          hasMoreNotes.set(false);
          notesLoaded = true;
          cacheLoadDone = true;
          notesLoadedOnce.set(true);
        }
      } catch (cacheErr) {
        logger.error('[notes] IndexedDB fallback failed:', cacheErr);
      }
    }
  } finally {
    notesLoading.set(false);
    pendingLoad = false;
  }
}

/**
 * Fetch the next page of notes (using `skip`) and append them to the existing
 * list. Resolves the "silent cap at 1000" issue (#648) by letting users load
 * older notes on demand.
 */
export async function loadMore(): Promise<void> {
  if (get(loadingMore) || !get(hasMoreNotes)) return;
  loadingMore.set(true);
  try {
    const skip = get(notes).length;
    const data = await api.notes.list(lastTag, NOTES_PAGE_SIZE, skip);
    if (data.length > 0) {
      // Append, de-duplicating by id in case of overlap.
      const existingIds = new Set(get(notes).map((n) => n.id));
      const fresh = data.filter((n) => !existingIds.has(n.id));
      notes.update((ns) => [...ns, ...fresh]);
      if (browser) {
        Promise.all(fresh.map((n) => putNote(n))).catch(() => {});
      }
    }
    hasMoreNotes.set(data.length >= NOTES_PAGE_SIZE);
  } catch (e) {
    logger.error('[notes] Failed to load more:', e);
    hasMoreNotes.set(false);
  } finally {
    loadingMore.set(false);
  }
}

export async function createNote(title: string, content: string, tags: string[], sourcePath?: string | null): Promise<Note | null> {
  // When offline, queue the change instead of failing.
  if (browser && !get(offlineIsOnline)) {
    try {
      const tempId = -Date.now();
      const tempNote: Note = {
        id: tempId,
        title,
        content,
        source: 'manual',
        source_path: sourcePath ?? null,
        tags,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      notes.update((ns) => [tempNote, ...ns]);
      await queueChange('create', tempNote);
      return tempNote;
    } catch (e) {
      logger.error('[notes] Failed to queue create while offline:', e);
      return null;
    }
  }

  try {
    const result = await api.notes.create({ title, content, tags, source_path: sourcePath ?? undefined });
    notes.update(ns => [result, ...ns]);
    applyGamificationResult(result.gamification);
    if (browser) putNote(result).catch(() => {});
    return result;
  } catch (e) {
    logger.error('[notes] Failed to create:', e);
    return null;
  }
}

export async function updateNote(id: number, data: Partial<{ title: string; content: string; tags: string[] }>): Promise<void> {
  // When offline, queue the change instead of failing.
  if (browser && !get(offlineIsOnline)) {
    try {
      const existing = get(notes).find((n) => n.id === id);
      if (!existing) {
        logger.error('[notes] Cannot update unknown note while offline:', id);
        return;
      }
      const updated: Note = {
        ...existing,
        title: data.title ?? existing.title,
        content: data.content ?? existing.content,
        tags: data.tags ?? existing.tags,
        updated_at: new Date().toISOString(),
      };
      notes.update((ns) => ns.map((n) => (n.id === id ? updated : n)));
      await queueChange('update', updated);
    } catch (e) {
      logger.error('[notes] Failed to queue update while offline:', e);
    }
    return;
  }

  try {
    const result = await api.notes.update(id, data);
    notes.update(ns => ns.map(n => (n.id === id ? result : n)));
    applyGamificationResult(result.gamification);
    if (browser) putNote(result).catch(() => {});
  } catch (e) {
    logger.error('[notes] Failed to update:', e);
  }
}

export async function deleteNote(id: number): Promise<void> {
  // When offline, queue the change instead of failing.
  if (browser && !get(offlineIsOnline)) {
    try {
      const existing = get(notes).find((n) => n.id === id);
      if (!existing) {
        logger.error('[notes] Cannot delete unknown note while offline:', id);
        return;
      }
      notes.update((ns) => ns.filter((n) => n.id !== id));
      currentNote.update((n) => (n?.id === id ? null : n));
      await queueChange('delete', existing);
    } catch (e) {
      logger.error('[notes] Failed to queue delete while offline:', e);
    }
    return;
  }

  try {
    await api.notes.delete(id);
    notes.update(ns => ns.filter(n => n.id !== id));
    currentNote.update(n => (n?.id === id ? null : n));
    if (browser) idbDeleteNote(id).catch(() => {});
  } catch (e) {
    logger.error('[notes] Failed to delete:', e);
  }
}

export function toggleNoteSelection(id: number) {
  selectedNoteIds.update(s => {
    const next = new Set(s);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });
}

export function selectAllNotes() {
  selectedNoteIds.update(() => new Set(get(notes).map(n => n.id)));
}

export function clearNoteSelection() {
  selectedNoteIds.update(() => new Set());
}

export async function deleteSelectedNotes(): Promise<void> {
  const ids = Array.from(get(selectedNoteIds));
  if (ids.length === 0) return;
  try {
    await api.notes.bulkDelete(ids);
    notes.update(ns => ns.filter(n => !ids.includes(n.id)));
    currentNote.update(n => (n && ids.includes(n.id)) ? null : n);
    clearNoteSelection();
  } catch (e) {
    logger.error('[notes] Failed to bulk delete:', e);
  }
}

export async function tagSelectedNotes(tags: string[]): Promise<void> {
  const ids = Array.from(get(selectedNoteIds));
  if (ids.length === 0 || tags.length === 0) return;
  try {
    await api.notes.bulkTag(ids, tags);
    notes.update(ns => ns.map(n => ids.includes(n.id) ? { ...n, tags: [...new Set([...n.tags, ...tags])] } : n));
  } catch (e) {
    logger.error('[notes] Failed to bulk tag:', e);
  }
}

export async function untagSelectedNotes(tags: string[]): Promise<void> {
  const ids = Array.from(get(selectedNoteIds));
  if (ids.length === 0 || tags.length === 0) return;
  try {
    await api.notes.bulkUntag(ids, tags);
    const tagSet = new Set(tags.map(t => t.toLowerCase().trim()));
    notes.update(ns => ns.map(n => ids.includes(n.id) ? { ...n, tags: n.tags.filter(t => !tagSet.has(t.toLowerCase().trim())) } : n));
  } catch (e) {
    logger.error('[notes] Failed to bulk untag:', e);
  }
}

export async function fetchAISuggestions(noteId: number, content: string, existingTags: string[]): Promise<void> {
  try {
    const result = await api.ai.classify(noteId, content, existingTags);
    aiSuggestions.set(result.suggestions ?? []);
  } catch (_) {
    aiSuggestions.set([]);
  }
}

/** Returns the first note matching the title or path (case insensitive) */
export function findNoteByTitle(title: string): Note | undefined {
  let found: Note | undefined;
  const clean = title.toLowerCase().trim();
  notes.subscribe(ns => {
    found = ns.find(n => 
      n.title.toLowerCase().trim() === clean ||
      (n.source_path && n.source_path.toLowerCase().includes(clean))
    );
  })();
  return found;
}

export const noteSearchQuery = writable('');
export const noteSearchTag = writable<string | null>(null);
export const noteSortBy = writable<'updated' | 'created' | 'title'>('updated');
export const noteSortAsc = writable(false);

export const filteredNotes = derived(
  [notes, noteSearchQuery, noteSearchTag, noteSortBy, noteSortAsc],
  ([$notes, $query, $tag, $sortBy, $sortAsc]) => {
    const q = $query.toLowerCase().trim();
    const filtered = $notes.filter(n => {
      const matchesQuery = !q || n.title.toLowerCase().includes(q) || n.content.toLowerCase().includes(q);
      const matchesTag = !$tag || n.tags.includes($tag);
      return matchesQuery && matchesTag;
    });

    return [...filtered].sort((a, b) => {
      let cmp = 0;
      if ($sortBy === 'title') cmp = a.title.localeCompare(b.title);
      else if ($sortBy === 'created') cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      else cmp = new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime();
      return $sortAsc ? cmp : -cmp;
    });
  }
);

