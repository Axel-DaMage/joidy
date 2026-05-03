import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';
import { api, type Note, type AISuggestion } from '$lib/api';
import { applyGamificationResult } from './gamification';

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
    console.error('[notes] Failed to load:', e);
  } finally {
    notesLoading.set(false);
    pendingLoad = false;
  }
}

export async function createNote(title: string, content: string, tags: string[]): Promise<Note | null> {
  try {
    const result = await api.notes.create({ title, content, tags });
    notes.update(ns => [result, ...ns]);
    applyGamificationResult(result.gamification);
    return result;
  } catch (e) {
    console.error('[notes] Failed to create:', e);
    return null;
  }
}

export async function updateNote(id: number, data: Partial<{ title: string; content: string; tags: string[] }>): Promise<void> {
  try {
    const result = await api.notes.update(id, data);
    notes.update(ns => ns.map(n => (n.id === id ? result : n)));
    applyGamificationResult(result.gamification);
  } catch (e) {
    console.error('[notes] Failed to update:', e);
  }
}

export async function deleteNote(id: number): Promise<void> {
  try {
    await api.notes.delete(id);
    notes.update(ns => ns.filter(n => n.id !== id));
    currentNote.update(n => (n?.id === id ? null : n));
  } catch (e) {
    console.error('[notes] Failed to delete:', e);
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

