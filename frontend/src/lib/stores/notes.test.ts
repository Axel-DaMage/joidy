import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

// Mock $app/environment so `browser` is true (jsdom provides sessionStorage).
vi.mock('$app/environment', () => ({ browser: true, dev: false }));

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    notes: {
      list: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
      bulkDelete: vi.fn(),
      bulkTag: vi.fn(),
      bulkUntag: vi.fn(),
    },
    ai: { classify: vi.fn() },
  },
}));

vi.mock('$lib/api', () => ({ api: apiMock }));

vi.mock('$lib/utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), log: vi.fn(), debug: vi.fn() },
}));

vi.mock('./gamification', () => ({
  applyGamificationResult: vi.fn(),
  // re-export the real stores that notes.test doesn't need, but gamification
  // module exports notifications; not needed here.
}));

import {
  notes,
  currentNote,
  aiSuggestions,
  notesLoading,
  notesLoadedOnce,
  selectedNoteIds,
  bulkMode,
  loadNotes,
  createNote,
  updateNote,
  deleteNote,
  toggleNoteSelection,
  selectAllNotes,
  clearNoteSelection,
  deleteSelectedNotes,
  tagSelectedNotes,
  untagSelectedNotes,
  fetchAISuggestions,
  findNoteByTitle,
  filteredNotes,
  noteSearchQuery,
  noteSearchTag,
  noteSortBy,
  noteSortAsc,
} from './notes';
import { applyGamificationResult } from './gamification';

function makeNote(overrides: Partial<any> = {}): any {
  return {
    id: 1,
    title: 'Test Note',
    content: 'Some content',
    source: 'manual',
    source_path: '/vault/test.md',
    tags: ['work'],
    created_at: '2024-01-01T10:00:00',
    updated_at: '2024-01-02T10:00:00',
    ...overrides,
  };
}

function resetState() {
  notes.set([]);
  currentNote.set(null);
  aiSuggestions.set([]);
  notesLoading.set(false);
  notesLoadedOnce.set(false);
  selectedNoteIds.set(new Set());
  bulkMode.set(false);
  noteSearchQuery.set('');
  noteSearchTag.set(null);
  noteSortBy.set('updated');
  noteSortAsc.set(false);
  sessionStorage.clear();
  vi.clearAllMocks();
  (applyGamificationResult as any).mockReset();
}

describe('loadNotes', () => {
  beforeEach(() => resetState());

  it('loads notes from the API and updates the store', async () => {
    const data = [makeNote({ id: 1 }), makeNote({ id: 2, title: 'Second' })];
    apiMock.notes.list.mockResolvedValue(data);
    await loadNotes();
    expect(get(notes)).toEqual(data);
    expect(get(notesLoadedOnce)).toBe(true);
    expect(get(notesLoading)).toBe(false);
  });

  it('passes the tag filter to the API', async () => {
    apiMock.notes.list.mockResolvedValue([]);
    await loadNotes('work');
    expect(apiMock.notes.list).toHaveBeenCalledWith('work', 200, 0);
  });

  it('does not throw when the API fails', async () => {
    apiMock.notes.list.mockRejectedValue(new Error('network'));
    await expect(loadNotes(undefined, true)).resolves.toBeUndefined();
    expect(get(notes)).toEqual([]);
  });

  it('uses cached notes from sessionStorage when available', async () => {
    const cached = [makeNote({ id: 9, title: 'Cached' })];
    sessionStorage.setItem(
      'joidy_notes_cache',
      JSON.stringify({ data: cached, ts: Date.now() })
    );
    apiMock.notes.list.mockResolvedValue([makeNote({ id: 1, title: 'Fresh' })]);
    await loadNotes();
    // Cache is applied first (instant), then fresh data overwrites
    expect(get(notes).length).toBe(1);
    expect(get(notes)[0].title).toBe('Fresh');
  });

  it('ignores stale cache older than 5 minutes', async () => {
    const stale = [makeNote({ id: 9, title: 'Stale' })];
    sessionStorage.setItem(
      'joidy_notes_cache',
      JSON.stringify({ data: stale, ts: Date.now() - 400000 })
    );
    apiMock.notes.list.mockResolvedValue([makeNote({ id: 1, title: 'Fresh' })]);
    await loadNotes();
    expect(get(notes)[0].title).toBe('Fresh');
  });
});

describe('findNoteByTitle', () => {
  beforeEach(() => resetState());

  it('finds a note by exact title (case insensitive)', () => {
    notes.set([makeNote({ id: 1, title: 'My Note' }), makeNote({ id: 2, title: 'Other' })]);
    expect(findNoteByTitle('my note')?.id).toBe(1);
  });

  it('finds a note by source_path substring', () => {
    notes.set([makeNote({ id: 1, title: 'A', source_path: '/vault/special.md' })]);
    expect(findNoteByTitle('special')?.id).toBe(1);
  });

  it('returns undefined when no match', () => {
    notes.set([makeNote({ id: 1, title: 'A' })]);
    expect(findNoteByTitle('nope')).toBeUndefined();
  });

  it('trims and lowercases the query', () => {
    notes.set([makeNote({ id: 1, title: 'Hello' })]);
    expect(findNoteByTitle('  HELLO  ')?.id).toBe(1);
  });
});

describe('createNote', () => {
  beforeEach(() => resetState());

  it('creates a note, prepends it and applies gamification', async () => {
    const created = makeNote({ id: 5, title: 'New', gamification: { xp_awarded: 10 } });
    apiMock.notes.create.mockResolvedValue(created);
    notes.set([makeNote({ id: 1 })]);
    const result = await createNote('New', 'body', ['tag']);
    expect(result?.id).toBe(5);
    expect(get(notes)[0].id).toBe(5);
    expect(applyGamificationResult).toHaveBeenCalled();
  });

  it('returns null when the API fails', async () => {
    apiMock.notes.create.mockRejectedValue(new Error('boom'));
    const result = await createNote('x', 'y', []);
    expect(result).toBeNull();
  });
});

describe('updateNote', () => {
  beforeEach(() => resetState());

  it('replaces the matching note in the store', async () => {
    notes.set([makeNote({ id: 1, title: 'Old' }), makeNote({ id: 2, title: 'Keep' })]);
    const updated = makeNote({ id: 1, title: 'New', gamification: { xp_awarded: 5 } });
    apiMock.notes.update.mockResolvedValue(updated);
    await updateNote(1, { title: 'New' });
    expect(get(notes).find(n => n.id === 1)?.title).toBe('New');
    expect(get(notes).find(n => n.id === 2)?.title).toBe('Keep');
    expect(applyGamificationResult).toHaveBeenCalled();
  });

  it('does not throw when the API fails', async () => {
    apiMock.notes.update.mockRejectedValue(new Error('boom'));
    await expect(updateNote(1, { title: 'x' })).resolves.toBeUndefined();
  });
});

describe('deleteNote', () => {
  beforeEach(() => resetState());

  it('removes the note from the store', async () => {
    notes.set([makeNote({ id: 1 }), makeNote({ id: 2 })]);
    apiMock.notes.delete.mockResolvedValue(undefined);
    await deleteNote(1);
    expect(get(notes).map(n => n.id)).toEqual([2]);
  });

  it('clears currentNote if it was the deleted one', async () => {
    const n = makeNote({ id: 1 });
    notes.set([n]);
    currentNote.set(n);
    apiMock.notes.delete.mockResolvedValue(undefined);
    await deleteNote(1);
    expect(get(currentNote)).toBeNull();
  });

  it('keeps currentNote if it was a different one', async () => {
    const a = makeNote({ id: 1 });
    const b = makeNote({ id: 2 });
    notes.set([a, b]);
    currentNote.set(b);
    apiMock.notes.delete.mockResolvedValue(undefined);
    await deleteNote(1);
    expect(get(currentNote)?.id).toBe(2);
  });
});

describe('selection / bulk operations', () => {
  beforeEach(() => resetState());

  it('toggleNoteSelection adds and removes ids', () => {
    toggleNoteSelection(1);
    expect(get(selectedNoteIds).has(1)).toBe(true);
    toggleNoteSelection(1);
    expect(get(selectedNoteIds).has(1)).toBe(false);
  });

  it('selectAllNotes selects all note ids', () => {
    notes.set([makeNote({ id: 1 }), makeNote({ id: 2 })]);
    selectAllNotes();
    expect(get(selectedNoteIds).size).toBe(2);
  });

  it('clearNoteSelection empties the set', () => {
    selectedNoteIds.set(new Set([1, 2]));
    clearNoteSelection();
    expect(get(selectedNoteIds).size).toBe(0);
  });

  it('deleteSelectedNotes removes selected and clears selection', async () => {
    notes.set([makeNote({ id: 1 }), makeNote({ id: 2 }), makeNote({ id: 3 })]);
    selectedNoteIds.set(new Set([1, 3]));
    apiMock.notes.bulkDelete.mockResolvedValue({ deleted: 2, total: 2 });
    await deleteSelectedNotes();
    expect(get(notes).map(n => n.id)).toEqual([2]);
    expect(get(selectedNoteIds).size).toBe(0);
  });

  it('deleteSelectedNotes does nothing with empty selection', async () => {
    await deleteSelectedNotes();
    expect(apiMock.notes.bulkDelete).not.toHaveBeenCalled();
  });

  it('tagSelectedNotes merges tags into selected notes', async () => {
    notes.set([makeNote({ id: 1, tags: ['a'] }), makeNote({ id: 2, tags: ['b'] })]);
    selectedNoteIds.set(new Set([1]));
    apiMock.notes.bulkTag.mockResolvedValue({ added: 1, notes: 1, tags: ['c'] });
    await tagSelectedNotes(['c']);
    expect(get(notes).find(n => n.id === 1)?.tags).toContain('c');
    expect(get(notes).find(n => n.id === 2)?.tags).not.toContain('c');
  });

  it('untagSelectedNotes removes tags from selected notes', async () => {
    notes.set([makeNote({ id: 1, tags: ['a', 'b'] }), makeNote({ id: 2, tags: ['a'] })]);
    selectedNoteIds.set(new Set([1]));
    apiMock.notes.bulkUntag.mockResolvedValue({ removed: 1, notes: 1, tags: ['a'] });
    await untagSelectedNotes(['a']);
    expect(get(notes).find(n => n.id === 1)?.tags).toEqual(['b']);
    expect(get(notes).find(n => n.id === 2)?.tags).toEqual(['a']);
  });
});

describe('fetchAISuggestions', () => {
  beforeEach(() => resetState());

  it('sets suggestions from the API', async () => {
    apiMock.ai.classify.mockResolvedValue({ suggestions: [{ tag: 'x', confidence: 0.9 }] });
    await fetchAISuggestions(1, 'content', []);
    expect(get(aiSuggestions).length).toBe(1);
  });

  it('clears suggestions on error', async () => {
    aiSuggestions.set([{ tag: 'old' } as any]);
    apiMock.ai.classify.mockRejectedValue(new Error('boom'));
    await fetchAISuggestions(1, 'content', []);
    expect(get(aiSuggestions)).toEqual([]);
  });
});

describe('filteredNotes (derived)', () => {
  beforeEach(() => resetState());

  it('filters by query in title and content', () => {
    notes.set([
      makeNote({ id: 1, title: 'Alpha', content: 'body', updated_at: '2024-01-01T00:00:00' }),
      makeNote({ id: 2, title: 'Beta', content: 'special', updated_at: '2024-01-02T00:00:00' }),
    ]);
    noteSearchQuery.set('special');
    expect(get(filteredNotes).map(n => n.id)).toEqual([2]);
  });

  it('filters by tag', () => {
    notes.set([
      makeNote({ id: 1, tags: ['work'], updated_at: '2024-01-01T00:00:00' }),
      makeNote({ id: 2, tags: ['personal'], updated_at: '2024-01-02T00:00:00' }),
    ]);
    noteSearchTag.set('work');
    expect(get(filteredNotes).map(n => n.id)).toEqual([1]);
  });

  it('sorts by updated desc by default', () => {
    notes.set([
      makeNote({ id: 1, updated_at: '2024-01-01T00:00:00' }),
      makeNote({ id: 2, updated_at: '2024-01-05T00:00:00' }),
    ]);
    noteSearchQuery.set('');
    noteSearchTag.set(null);
    expect(get(filteredNotes).map(n => n.id)).toEqual([2, 1]);
  });

  it('sorts by title ascending', () => {
    notes.set([
      makeNote({ id: 1, title: 'Zebra', updated_at: '2024-01-01T00:00:00' }),
      makeNote({ id: 2, title: 'Apple', updated_at: '2024-01-02T00:00:00' }),
    ]);
    noteSortBy.set('title');
    noteSortAsc.set(true);
    expect(get(filteredNotes).map(n => n.id)).toEqual([2, 1]);
  });
});
