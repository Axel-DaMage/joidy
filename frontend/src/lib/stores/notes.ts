import { writable } from 'svelte/store';
import { api, type Note, type AISuggestion } from '$lib/api';
import { applyGamificationResult } from './gamification';

export const notes        = writable<Note[]>([]);
export const currentNote  = writable<Note | null>(null);
export const aiSuggestions = writable<AISuggestion[]>([]);
export const notesLoading  = writable(false);

export async function loadNotes(tag?: string): Promise<void> {
  notesLoading.set(true);
  try {
    const data = await api.notes.list(tag);
    notes.set(data);
  } catch (e) {
    console.error('[notes] Failed to load:', e);
  } finally {
    notesLoading.set(false);
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
