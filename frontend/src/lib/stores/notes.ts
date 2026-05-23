import { writable, get, derived } from 'svelte/store';
import { browser } from '$app/environment';
import { api, type Note, type AISuggestion } from '$lib/api';
import { applyGamificationResult } from './gamification';
import { logger } from '$lib/utils/logger';

export const notes        = writable<Note[]>([]);
export const currentNote  = writable<Note | null>(null);
export const aiSuggestions = writable<AISuggestion[]>([]);
export const notesLoading  = writable(false);
export const notesLoadedOnce = writable(false);

let notesLoaded = false;
let lastTag: string | undefined = undefined;
let pendingLoad = false;
let cacheLoadDone = false;

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
    const data = await api.notes.list(tag);
    notes.set(data);
    saveNotesCache(data);
    notesLoaded = true;
    cacheLoadDone = true;
    notesLoadedOnce.set(true);
  } catch (e) {
    logger.error('[notes] Failed to load:', e);
  } finally {
    notesLoading.set(false);
    pendingLoad = false;
  }
}

export async function createNote(title: string, content: string, tags: string[], sourcePath?: string | null): Promise<Note | null> {
  try {
    const result = await api.notes.create({ title, content, tags, source_path: sourcePath ?? undefined });
    notes.update(ns => [result, ...ns]);
    applyGamificationResult(result.gamification);
    return result;
  } catch (e) {
    logger.error('[notes] Failed to create:', e);
    return null;
  }
}

export async function updateNote(id: number, data: Partial<{ title: string; content: string; tags: string[] }>): Promise<void> {
  try {
    const result = await api.notes.update(id, data);
    notes.update(ns => ns.map(n => (n.id === id ? result : n)));
    applyGamificationResult(result.gamification);
  } catch (e) {
    logger.error('[notes] Failed to update:', e);
  }
}

export async function deleteNote(id: number): Promise<void> {
  try {
    await api.notes.delete(id);
    notes.update(ns => ns.filter(n => n.id !== id));
    currentNote.update(n => (n?.id === id ? null : n));
  } catch (e) {
    logger.error('[notes] Failed to delete:', e);
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

