// localStorage draft persistence extracted from NoteEditor.svelte (#210).

export interface NoteDraft {
  title: string;
  content: string;
  tags: string[];
  savedAt: number;
}

export function loadDraft(draftKey: string | null): NoteDraft | null {
  if (!draftKey) return null;
  try {
    const raw = localStorage.getItem(draftKey);
    if (raw) {
      const draft = JSON.parse(raw);
      if (draft && draft.content) return draft as NoteDraft;
    }
  } catch {}
  return null;
}

export function persistDraft(draftKey: string | null, draft: Omit<NoteDraft, 'savedAt'>) {
  if (!draftKey) return;
  try {
    localStorage.setItem(draftKey, JSON.stringify({ ...draft, savedAt: Date.now() }));
  } catch {}
}

export function clearDraft(draftKey: string | null) {
  if (draftKey) {
    try {
      localStorage.removeItem(draftKey);
    } catch {}
  }
}
