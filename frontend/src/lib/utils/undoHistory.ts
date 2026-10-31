// Snapshot-based undo history extracted from NoteEditor.svelte (#210).
// Plain (non-reactive) class — history state is never rendered directly.

export class UndoHistory {
  stack: string[] = [''];
  index = 0;
  lock = false;
  private saveTimeout: ReturnType<typeof setTimeout> | undefined;

  reset(initial: string) {
    this.stack = [initial || ''];
    this.index = 0;
  }

  push(cur: string) {
    if (this.lock) return;
    if (this.stack[this.index] === cur) return;
    this.stack = this.stack.slice(0, this.index + 1);
    this.stack.push(cur);
    if (this.stack.length > 100) this.stack.shift();
    this.index = this.stack.length - 1;
  }

  // Debounced snapshot (600ms) — callers pass a getter so the current content
  // is read when the timeout fires, not when scheduled.
  schedule(getContent: () => string) {
    clearTimeout(this.saveTimeout);
    this.saveTimeout = setTimeout(() => this.push(getContent()), 600);
  }

  undo(): string | undefined {
    if (this.index <= 0) return undefined;
    this.index--;
    this.lock = true;
    const snapshot = this.stack[this.index];
    this.lock = false;
    return snapshot;
  }

  redo(): string | undefined {
    if (this.index >= this.stack.length - 1) return undefined;
    this.index++;
    this.lock = true;
    const snapshot = this.stack[this.index];
    this.lock = false;
    return snapshot;
  }

  clear() {
    clearTimeout(this.saveTimeout);
  }
}
