// Global editor keyboard shortcuts extracted from NoteEditor.svelte (#210).

export interface EditorKeyContext {
  save: () => void;
  undo: () => void;
  redo: () => void;
  togglePreview: () => void;
  toggleWysiwyg: () => void;
  exitZen: () => void;
  zenMode: boolean;
  hasPrev: boolean;
  hasNext: boolean;
  prev: () => void;
  next: () => void;
}

export function handleEditorKeydown(e: KeyboardEvent, ctx: EditorKeyContext) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault();
    ctx.save();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
    e.preventDefault();
    ctx.togglePreview();
  }
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'v') {
    e.preventDefault();
    ctx.toggleWysiwyg();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
    if (e.shiftKey) {
      e.preventDefault();
      ctx.redo();
    } else {
      e.preventDefault();
      ctx.undo();
    }
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'y') {
    e.preventDefault();
    ctx.redo();
  }
  if (e.key === 'Escape' && ctx.zenMode) {
    e.preventDefault();
    e.stopPropagation();
    ctx.exitZen();
  }
  if (e.altKey && e.key === 'ArrowLeft' && ctx.hasPrev) {
    e.preventDefault();
    ctx.prev();
  }
  if (e.altKey && e.key === 'ArrowRight' && ctx.hasNext) {
    e.preventDefault();
    ctx.next();
  }
}
