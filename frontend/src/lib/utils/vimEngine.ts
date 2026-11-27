// Pure vim-style modal editing state machine (#1666).
//
// The engine never touches the DOM: callers feed it a key event plus the
// textarea's current { text, start, end } and apply the returned result
// (caret move, content edit, mode transition, or an undo/redo action mapped
// to the editor's existing UndoHistory). Operating on the *visible* buffer
// keeps it agnostic of the frontmatter/tags-line hiding done by
// `recomposeHiddenSlices` — the component recomposes after every edit.
//
// Not implemented (documented limitations): counts (`3dd`), VISUAL mode,
// named registers, macros, text objects, `.` repeat. `p` pastes the engine's
// own linewise/charwise register, not the OS clipboard.

export type VimMode = 'normal' | 'insert';

export interface VimBuffer {
  /** Full text of the editable buffer (visible editor content). */
  text: string;
  /** Selection start (caret when collapsed). */
  start: number;
  /** Selection end. */
  end: number;
}

export interface VimKey {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
  /** IME composition guard — callers must also check `e.isComposing`. */
  isComposing?: boolean;
}

export interface VimEdit {
  /** New buffer content after the edit. */
  text: string;
  /** Caret position in the new buffer. */
  caret: number;
}

export interface VimResult {
  /** Whether the key was consumed (preventDefault + stopPropagation). */
  handled: boolean;
  /** Mode transition to apply, if any. */
  mode?: VimMode;
  /** Pure caret move (no content change). */
  caret?: number;
  /** Buffer mutation (content + caret). */
  edit?: VimEdit;
  /** Editor-level action delegated to the host (undo/redo history). */
  action?: 'undo' | 'redo';
}

const HANDLED: VimResult = { handled: true };
const PASS: VimResult = { handled: false };

function isWordChar(c: string): boolean {
  return /\w/.test(c);
}

function isSpace(c: string): boolean {
  return /\s/.test(c);
}

// Character classes for word motions: 0 = word, 1 = punctuation, 2 = space.
function charClass(c: string): number {
  if (isWordChar(c)) return 0;
  if (isSpace(c)) return 2;
  return 1;
}

/** Index of the first char of the line containing `pos`. */
export function lineStart(text: string, pos: number): number {
  if (pos <= 0) return 0;
  const i = text.lastIndexOf('\n', pos - 1);
  return i < 0 ? 0 : i + 1;
}

/** Index of the '\n' ending the line containing `pos` (or text.length). */
export function lineEnd(text: string, pos: number): number {
  const i = text.indexOf('\n', pos);
  return i < 0 ? text.length : i;
}

/** First non-blank char of the line bounded by [ls, le). */
function firstNonBlank(text: string, ls: number, le: number): number {
  let i = ls;
  while (i < le && (text[i] === ' ' || text[i] === '\t')) i++;
  return i;
}

/** `w`: start of the next word; clamps to the last char at EOF. */
function wordForward(text: string, pos: number): number {
  const n = text.length;
  if (n === 0) return 0;
  let i = Math.min(pos, n - 1);
  const c0 = charClass(text[i]);
  if (c0 !== 2) {
    while (i < n && charClass(text[i]) === c0) i++;
  }
  while (i < n && isSpace(text[i])) i++;
  return Math.min(i, n - 1);
}

/** `b`: start of the previous word. */
function wordBackward(text: string, pos: number): number {
  let i = pos - 1;
  while (i > 0 && isSpace(text[i])) i--;
  if (i <= 0) return 0;
  const c0 = charClass(text[i]);
  while (i > 0 && charClass(text[i - 1]) === c0) i--;
  return i;
}

/** `e`: last char of the current/next word. */
function wordEnd(text: string, pos: number): number {
  const n = text.length;
  if (n === 0) return 0;
  let i = pos + 1;
  while (i < n && isSpace(text[i])) i++;
  if (i >= n) return n - 1;
  const c0 = charClass(text[i]);
  while (i < n - 1 && charClass(text[i + 1]) === c0) i++;
  return i;
}

export class VimEngine {
  mode: VimMode = 'normal';

  private pending = '';
  private register = '';
  private registerLinewise = false;
  private goalColumn: number | null = null;

  /** First key of a pending two-key sequence (`d`, `y`, `g`, `>`, `<`). */
  get pendingKey(): string {
    return this.pending;
  }

  /** Last yanked/deleted text (diagnostics/testing). */
  get registerText(): string {
    return this.register;
  }

  get registerIsLinewise(): boolean {
    return this.registerLinewise;
  }

  reset(): void {
    this.mode = 'normal';
    this.pending = '';
    this.goalColumn = null;
  }

  handleKey(k: VimKey, buf: VimBuffer): VimResult {
    if (k.isComposing) return PASS;
    const text = buf.text;
    const pos = Math.min(Math.max(0, buf.start), text.length);
    if (this.mode === 'insert') return this.handleInsert(k, text, pos);
    return this.handleNormal(k, text, pos);
  }

  private handleInsert(k: VimKey, text: string, pos: number): VimResult {
    if (k.key === 'Escape' || (k.ctrlKey && k.key === '[')) {
      // Vim pulls the caret one char left when leaving insert mode so the
      // block cursor lands *on* a character instead of past EOL.
      const ls = lineStart(text, pos);
      return { handled: true, mode: 'normal', caret: pos > ls ? pos - 1 : pos };
    }
    return PASS;
  }

  private handleNormal(k: VimKey, text: string, pos: number): VimResult {
    if (this.pending) {
      const p = this.pending;
      this.pending = '';
      return this.resolvePending(p, k, text, pos);
    }

    if (k.ctrlKey || k.metaKey) {
      // Ctrl+R = redo; every other modifier combo (Ctrl+S, Ctrl+P, ...) is
      // left to the editor's global shortcuts.
      if (k.ctrlKey && (k.key === 'r' || k.key === 'R')) return { handled: true, action: 'redo' };
      return PASS;
    }
    if (k.altKey) return PASS;

    const keepGoal = k.key === 'j' || k.key === 'k' || k.key === 'ArrowDown' || k.key === 'ArrowUp';
    if (!keepGoal) this.goalColumn = null;

    const ls = lineStart(text, pos);
    const le = lineEnd(text, pos);
    // Last valid caret of the line (block cursor sits *on* a char).
    const lastOfLine = le > ls ? le - 1 : ls;

    switch (k.key) {
      case 'h':
      case 'ArrowLeft':
      case 'Backspace':
        return { handled: true, caret: pos > ls ? pos - 1 : pos };
      case 'l':
      case 'ArrowRight':
      case ' ':
        return { handled: true, caret: Math.min(pos + 1, lastOfLine) };
      case 'j':
      case 'ArrowDown':
        return this.moveVertical(text, pos, ls, le, 1);
      case 'k':
      case 'ArrowUp':
        return this.moveVertical(text, pos, ls, le, -1);
      case '0':
      case 'Home':
        return { handled: true, caret: ls };
      case '^':
        return { handled: true, caret: firstNonBlank(text, ls, le) };
      case '$':
      case 'End':
        return { handled: true, caret: lastOfLine };
      case 'w':
        return { handled: true, caret: wordForward(text, pos) };
      case 'b':
        return { handled: true, caret: wordBackward(text, pos) };
      case 'e':
        return { handled: true, caret: wordEnd(text, pos) };
      case 'G': {
        const gls = lineStart(text, text.length);
        return { handled: true, caret: firstNonBlank(text, gls, lineEnd(text, gls)) };
      }
      case 'g':
      case 'd':
      case 'y':
      case '>':
      case '<':
        this.pending = k.key;
        return HANDLED;
      case 'x':
      case 'Delete':
        if (pos >= le) return HANDLED;
        return this.deleteRange(text, pos, pos + 1);
      case 'p':
        return this.paste(text, pos, ls, le, false);
      case 'P':
        return this.paste(text, pos, ls, le, true);
      case 'u':
        return { handled: true, action: 'undo' };
      case 'i':
        return { handled: true, mode: 'insert' };
      case 'a':
        return { handled: true, mode: 'insert', caret: Math.min(pos + 1, le) };
      case 'A':
        return { handled: true, mode: 'insert', caret: le };
      case 'I':
        return { handled: true, mode: 'insert', caret: firstNonBlank(text, ls, le) };
      case 'o':
        return {
          handled: true,
          mode: 'insert',
          edit: { text: text.slice(0, le) + '\n' + text.slice(le), caret: le + 1 },
        };
      case 'O':
        return {
          handled: true,
          mode: 'insert',
          edit: { text: text.slice(0, ls) + '\n' + text.slice(ls), caret: ls },
        };
      case 'Escape':
        // No pending sequence: let the event bubble (zen-mode Esc etc.).
        return PASS;
      default:
        // Swallow printable keys so normal mode never inserts text; let
        // non-printable keys (F5, PageUp, ...) pass through untouched.
        if (k.key.length === 1 || k.key === 'Enter' || k.key === 'Tab') return HANDLED;
        return PASS;
    }
  }

  private moveVertical(
    text: string,
    pos: number,
    ls: number,
    le: number,
    dir: 1 | -1
  ): VimResult {
    const col = this.goalColumn ?? pos - ls;
    this.goalColumn = col;
    if (dir === 1) {
      if (le >= text.length) return HANDLED; // already on last line
      const nls = le + 1;
      const nle = lineEnd(text, nls);
      const maxOff = nle > nls ? nle - nls - 1 : 0;
      return { handled: true, caret: nls + Math.min(col, maxOff) };
    }
    if (ls === 0) return HANDLED; // already on first line
    const ple = ls - 1;
    const pls = lineStart(text, ple);
    const maxOff = ple > pls ? ple - pls - 1 : 0;
    return { handled: true, caret: pls + Math.min(col, maxOff) };
  }

  private resolvePending(p: string, k: VimKey, text: string, pos: number): VimResult {
    if (k.key === 'Escape') return HANDLED;

    const ls = lineStart(text, pos);
    const le = lineEnd(text, pos);

    if (k.key === p) {
      switch (p) {
        case 'g':
          return { handled: true, caret: firstNonBlank(text, 0, lineEnd(text, 0)) };
        case 'd':
          return this.deleteLines(text, ls, le);
        case 'y':
          this.yankLines(text, ls, le);
          return HANDLED;
        case '>':
          return this.indentLines(text, pos, ls, 1);
        case '<':
          return this.indentLines(text, pos, ls, -1);
      }
    }

    // Operator + motion: d/y followed by a movement key.
    if (p === 'd' || p === 'y') {
      const range = this.motionRange(k.key, text, pos, ls, le);
      if (range) {
        if (p === 'y') {
          this.register = text.slice(range.start, range.end);
          this.registerLinewise = range.linewise;
          return { handled: true, caret: pos };
        }
        if (range.linewise) return this.deleteLines(text, range.start, range.end);
        return this.deleteRange(text, range.start, range.end);
      }
    }

    // Unknown sequence: cancel it (vim discards the second key too).
    return HANDLED;
  }

  /**
   * Resolve an operator-motion (`dw`, `y$`, `dG`, ...) to a [start, end)
   * range, or null when the key is not a supported motion. `linewise` marks
   * full-line ranges so the operator includes newlines correctly.
   */
  private motionRange(
    key: string,
    text: string,
    pos: number,
    ls: number,
    le: number
  ): { start: number; end: number; linewise: boolean } | null {
    switch (key) {
      case 'w': {
        const t = wordForward(text, pos);
        if (t <= pos) return null;
        return { start: pos, end: t, linewise: false };
      }
      case 'b': {
        const t = wordBackward(text, pos);
        if (t >= pos) return null;
        return { start: t, end: pos, linewise: false };
      }
      case 'e': {
        const t = wordEnd(text, pos);
        return { start: pos, end: Math.min(t + 1, text.length), linewise: false };
      }
      case '$':
        return { start: pos, end: le, linewise: false };
      case '0':
        return { start: ls, end: pos, linewise: false };
      case '^': {
        const t = firstNonBlank(text, ls, le);
        if (t >= pos) return null;
        return { start: t, end: pos, linewise: false };
      }
      case 'h':
      case 'l':
        // Charwise single-char motions: `dl` ≡ `x`, `dh` deletes the left char.
        if (key === 'l' && pos < le) return { start: pos, end: pos + 1, linewise: false };
        if (key === 'h' && pos > ls) return { start: pos - 1, end: pos, linewise: false };
        return null;
      case 'G': {
        const gls = lineStart(text, text.length);
        return { start: ls, end: lineEnd(text, gls), linewise: true };
      }
      default:
        return null;
    }
  }

  /** Charwise delete of [start, end); caret lands on the char after the cut. */
  private deleteRange(text: string, start: number, end: number): VimResult {
    if (end <= start) return HANDLED;
    this.register = text.slice(start, end);
    this.registerLinewise = false;
    const next = text.slice(0, start) + text.slice(end);
    const nls = lineStart(next, start);
    const nle = lineEnd(next, start);
    const caret = Math.min(start, nle > nls ? nle - 1 : nls);
    return { handled: true, edit: { text: next, caret } };
  }

  /** Linewise delete of the full lines covering [start, end]. */
  private deleteLines(text: string, start: number, end: number): VimResult {
    const ls = lineStart(text, start);
    const le = lineEnd(text, Math.min(end, text.length));
    let delStart = ls;
    let delEnd = le;
    if (le < text.length) {
      delEnd = le + 1; // include the trailing newline
    } else if (ls > 0) {
      delStart = ls - 1; // last line without newline: eat the previous one
    }
    const removed = text.slice(delStart, delEnd);
    // Normalize the register to whole lines without a trailing newline.
    this.register = removed.replace(/\n$/, '');
    this.registerLinewise = true;
    const next = text.slice(0, delStart) + text.slice(delEnd);
    const nls = lineStart(next, Math.min(delStart, next.length));
    const nle = lineEnd(next, nls);
    return {
      handled: true,
      edit: { text: next, caret: firstNonBlank(next, nls, nle) },
    };
  }

  private yankLines(text: string, start: number, end: number): void {
    const ls = lineStart(text, start);
    const le = lineEnd(text, Math.min(end, text.length));
    this.register = text.slice(ls, le);
    this.registerLinewise = true;
  }

  /** `p`/`P`: paste the internal register. System clipboard is out of scope. */
  private paste(text: string, pos: number, ls: number, le: number, before: boolean): VimResult {
    if (!this.register) return HANDLED;
    if (this.registerLinewise) {
      if (before) {
        const insert = this.register + '\n';
        return {
          handled: true,
          edit: { text: text.slice(0, ls) + insert + text.slice(ls), caret: ls },
        };
      }
      if (le < text.length) {
        const insertPos = le + 1;
        const insert = this.register + '\n';
        const next = text.slice(0, insertPos) + insert + text.slice(insertPos);
        const nls = insertPos;
        const nle = lineEnd(next, nls);
        return {
          handled: true,
          edit: { text: next, caret: firstNonBlank(next, nls, nle) },
        };
      }
      // Last line has no trailing newline — append one first.
      const insertPos = text.length;
      const next = text + '\n' + this.register;
      return { handled: true, edit: { text: next, caret: insertPos + 1 } };
    }
    const insertPos = before ? pos : Math.min(pos + 1, text.length);
    const next = text.slice(0, insertPos) + this.register + text.slice(insertPos);
    return { handled: true, edit: { text: next, caret: insertPos + this.register.length - 1 } };
  }

  /** `>>` (dir=1) / `<<` (dir=-1) on the caret's line. */
  private indentLines(text: string, pos: number, ls: number, dir: 1 | -1): VimResult {
    if (dir === 1) {
      return {
        handled: true,
        edit: { text: text.slice(0, ls) + '  ' + text.slice(ls), caret: pos + 2 },
      };
    }
    let n = 0;
    while (n < 2 && text[ls + n] === ' ') n++;
    if (n === 0 && text[ls] === '\t') n = 1;
    if (n === 0) return HANDLED;
    return {
      handled: true,
      edit: { text: text.slice(0, ls) + text.slice(ls + n), caret: Math.max(ls, pos - n) },
    };
  }
}
