import { describe, it, expect } from 'vitest';

import { VimEngine, lineStart, lineEnd, type VimKey, type VimBuffer } from './vimEngine';

function buf(text: string, start: number, end = start): VimBuffer {
  return { text, start, end };
}

function key(k: string, mods: Partial<VimKey> = {}): VimKey {
  return { key: k, ...mods };
}

describe('line helpers', () => {
  const text = 'ab\ncd\nef';

  it('lineStart returns the first index of the containing line', () => {
    expect(lineStart(text, 0)).toBe(0);
    expect(lineStart(text, 2)).toBe(0);
    expect(lineStart(text, 3)).toBe(3);
    expect(lineStart(text, 4)).toBe(3);
    expect(lineStart(text, 6)).toBe(6);
  });

  it('lineEnd returns the newline index (or text length)', () => {
    expect(lineEnd(text, 0)).toBe(2);
    expect(lineEnd(text, 3)).toBe(5);
    expect(lineEnd(text, 6)).toBe(8);
  });
});

describe('VimEngine — mode transitions', () => {
  it('starts in normal mode', () => {
    expect(new VimEngine().mode).toBe('normal');
  });

  it('i enters insert mode; Escape returns to normal', () => {
    const v = new VimEngine();
    const r1 = v.handleKey(key('i'), buf('abc', 1));
    expect(r1.handled).toBe(true);
    expect(r1.mode).toBe('insert');
    expect(v.mode).toBe('normal'); // mode is applied by the host, not the engine
    v.mode = 'insert';
    const r2 = v.handleKey(key('Escape'), buf('abc', 2));
    expect(r2.handled).toBe(true);
    expect(r2.mode).toBe('normal');
    expect(r2.caret).toBe(1); // caret pulled one char left (vim behavior)
  });

  it('Ctrl+[ also exits insert mode', () => {
    const v = new VimEngine();
    v.mode = 'insert';
    const r = v.handleKey(key('[', { ctrlKey: true }), buf('abc', 1));
    expect(r.handled).toBe(true);
    expect(r.mode).toBe('normal');
  });

  it('insert mode passes regular keys through untouched', () => {
    const v = new VimEngine();
    v.mode = 'insert';
    expect(v.handleKey(key('x'), buf('abc', 1)).handled).toBe(false);
    expect(v.handleKey(key('s', { ctrlKey: true }), buf('abc', 1)).handled).toBe(false);
  });

  it('Escape on an empty normal-mode buffer stays put', () => {
    const v = new VimEngine();
    v.mode = 'insert';
    const r = v.handleKey(key('Escape'), buf('', 0));
    expect(r.caret).toBe(0);
  });
});

describe('VimEngine — IME guard', () => {
  it('ignores keys while composing (normal and insert)', () => {
    const v = new VimEngine();
    expect(v.handleKey(key('j', { isComposing: true }), buf('a\nb', 0)).handled).toBe(false);
    v.mode = 'insert';
    expect(v.handleKey(key('Escape', { isComposing: true }), buf('a', 1)).handled).toBe(false);
  });
});

describe('VimEngine — normal motions', () => {
  const text = 'one two\nthree four\n\nfive';

  it('h/l move horizontally and clamp at line bounds', () => {
    const v = new VimEngine();
    expect(v.handleKey(key('h'), buf(text, 1)).caret).toBe(0);
    expect(v.handleKey(key('h'), buf(text, 0)).caret).toBe(0); // clamps at col 0
    expect(v.handleKey(key('l'), buf(text, 0)).caret).toBe(1);
    // "one two" last char is index 6 — l clamps on it
    expect(v.handleKey(key('l'), buf(text, 6)).caret).toBe(6);
  });

  it('j/k move vertically keeping the goal column and clamp at short lines', () => {
    const v = new VimEngine();
    expect(v.handleKey(key('j'), buf(text, 5)).caret).toBe(13); // col 5 → "three four"
    expect(v.handleKey(key('j'), buf(text, 13)).caret).toBe(19); // empty line
    // goal column 5 is preserved across the empty line, then clamps to "five"'s last char
    expect(v.handleKey(key('j'), buf(text, 19)).caret).toBe(23);
    expect(v.handleKey(key('k'), buf(text, 23)).caret).toBe(19);
  });

  it('j does nothing on the last line, k nothing on the first', () => {
    const v = new VimEngine();
    expect(v.handleKey(key('j'), buf(text, 20)).caret).toBeUndefined();
    expect(v.handleKey(key('k'), buf(text, 0)).caret).toBeUndefined();
  });

  it('arrow keys mirror h/j/k/l', () => {
    const v = new VimEngine();
    expect(v.handleKey(key('ArrowLeft'), buf(text, 1)).caret).toBe(0);
    expect(v.handleKey(key('ArrowRight'), buf(text, 0)).caret).toBe(1);
    expect(v.handleKey(key('ArrowDown'), buf(text, 0)).caret).toBe(8);
    expect(v.handleKey(key('ArrowUp'), buf(text, 8)).caret).toBe(0);
  });

  it('0 ^ $ jump within the line', () => {
    const v = new VimEngine();
    const t = '  indented\nnext';
    expect(v.handleKey(key('0'), buf(t, 5)).caret).toBe(0);
    expect(v.handleKey(key('^'), buf(t, 5)).caret).toBe(2);
    expect(v.handleKey(key('$'), buf(t, 0)).caret).toBe(9);
  });

  it('w/b/e word motions', () => {
    const v = new VimEngine();
    const t = 'foo bar\nbaz';
    expect(v.handleKey(key('w'), buf(t, 0)).caret).toBe(4);
    expect(v.handleKey(key('w'), buf(t, 4)).caret).toBe(8); // crosses newline
    expect(v.handleKey(key('b'), buf(t, 8)).caret).toBe(4);
    expect(v.handleKey(key('e'), buf(t, 0)).caret).toBe(2);
    expect(v.handleKey(key('e'), buf(t, 2)).caret).toBe(6);
  });

  it('gg / G jump to first / last line first-non-blank', () => {
    const v = new VimEngine();
    const t = '  first\nmid\n  last';
    v.handleKey(key('g'), buf(t, 8));
    expect(v.pendingKey).toBe('g');
    expect(v.handleKey(key('g'), buf(t, 8)).caret).toBe(2);
    expect(v.handleKey(key('G'), buf(t, 0)).caret).toBe(14);
  });

  it('Escape cancels a pending sequence without passing through', () => {
    const v = new VimEngine();
    v.handleKey(key('d'), buf(text, 0));
    const r = v.handleKey(key('Escape'), buf(text, 0));
    expect(r.handled).toBe(true);
    expect(v.pendingKey).toBe('');
  });

  it('invalid second key cancels the pending operator', () => {
    const v = new VimEngine();
    v.handleKey(key('d'), buf(text, 0));
    const r = v.handleKey(key('z'), buf(text, 0));
    expect(r.handled).toBe(true);
    expect(r.edit).toBeUndefined();
    expect(v.pendingKey).toBe('');
  });

  it('unmapped printable keys are swallowed, not inserted', () => {
    const v = new VimEngine();
    const r = v.handleKey(key('z'), buf(text, 0));
    expect(r.handled).toBe(true);
    expect(r.edit).toBeUndefined();
  });

  it('modifier combos other than Ctrl+R pass through to global shortcuts', () => {
    const v = new VimEngine();
    expect(v.handleKey(key('s', { ctrlKey: true }), buf(text, 0)).handled).toBe(false);
    expect(v.handleKey(key('p', { metaKey: true }), buf(text, 0)).handled).toBe(false);
    expect(v.handleKey(key('ArrowLeft', { altKey: true }), buf(text, 0)).handled).toBe(false);
  });
});

describe('VimEngine — editing', () => {
  const text = 'one two\nthree four\nfive';

  it('x deletes the char under the caret', () => {
    const v = new VimEngine();
    const r = v.handleKey(key('x'), buf(text, 0));
    expect(r.edit?.text).toBe('ne two\nthree four\nfive');
    expect(r.edit?.caret).toBe(0);
    expect(v.registerText).toBe('o');
  });

  it('dd deletes the current line including its newline', () => {
    const v = new VimEngine();
    v.handleKey(key('d'), buf(text, 9));
    const r = v.handleKey(key('d'), buf(text, 9));
    expect(r.edit?.text).toBe('one two\nfive');
    expect(r.edit?.caret).toBe(8);
    expect(v.registerText).toBe('three four');
    expect(v.registerIsLinewise).toBe(true);
  });

  it('dd on the last line eats the preceding newline', () => {
    const v = new VimEngine();
    v.handleKey(key('d'), buf(text, 20));
    const r = v.handleKey(key('d'), buf(text, 20));
    expect(r.edit?.text).toBe('one two\nthree four');
    expect(r.edit?.caret).toBe(8);
  });

  it('yy yanks the line and p pastes it below', () => {
    const v = new VimEngine();
    v.handleKey(key('y'), buf(text, 0));
    v.handleKey(key('y'), buf(text, 0));
    expect(v.registerText).toBe('one two');
    const r = v.handleKey(key('p'), buf(text, 0));
    expect(r.edit?.text).toBe('one two\none two\nthree four\nfive');
    expect(r.edit?.caret).toBe(8);
  });

  it('p after charwise delete pastes after the caret', () => {
    const v = new VimEngine();
    v.handleKey(key('x'), buf(text, 0)); // register 'o'
    const r = v.handleKey(key('p'), buf('ne two\nthree four\nfive', 0));
    expect(r.edit?.text).toBe('noe two\nthree four\nfive');
  });

  it('dw / y$ operator+motion combos', () => {
    const v = new VimEngine();
    v.handleKey(key('d'), buf(text, 0));
    const r = v.handleKey(key('w'), buf(text, 0));
    expect(r.edit?.text).toBe('two\nthree four\nfive');
    v.handleKey(key('y'), buf(text, 0));
    const r2 = v.handleKey(key('$'), buf(text, 0));
    expect(r2.caret).toBe(0);
    expect(v.registerText).toBe('one two');
    expect(v.registerIsLinewise).toBe(false);
  });

  it('>> indents and << removes up to two leading spaces', () => {
    const v = new VimEngine();
    v.handleKey(key('>'), buf('line', 0));
    const r = v.handleKey(key('>'), buf('line', 0));
    expect(r.edit?.text).toBe('  line');
    expect(r.edit?.caret).toBe(2);
    v.handleKey(key('<'), buf('   deep', 4));
    const r2 = v.handleKey(key('<'), buf('   deep', 4));
    expect(r2.edit?.text).toBe(' deep');
  });

  it('o/O open a line below/above and enter insert', () => {
    const v = new VimEngine();
    const r = v.handleKey(key('o'), buf(text, 0));
    expect(r.mode).toBe('insert');
    expect(r.edit?.text).toBe('one two\n\nthree four\nfive');
    expect(r.edit?.caret).toBe(8);
    const r2 = v.handleKey(key('O'), buf(text, 9));
    expect(r2.mode).toBe('insert');
    expect(r2.edit?.text).toBe('one two\n\nthree four\nfive');
    expect(r2.edit?.caret).toBe(8);
  });

  it('a/A/I enter insert at the right positions', () => {
    const v = new VimEngine();
    expect(v.handleKey(key('a'), buf(text, 0)).caret).toBe(1);
    expect(v.handleKey(key('A'), buf(text, 0)).caret).toBe(7);
    expect(v.handleKey(key('I'), buf('  ind', 4)).caret).toBe(2);
  });

  it('u and Ctrl+R delegate to the host undo/redo', () => {
    const v = new VimEngine();
    expect(v.handleKey(key('u'), buf(text, 0)).action).toBe('undo');
    expect(v.handleKey(key('r', { ctrlKey: true }), buf(text, 0)).action).toBe('redo');
  });

  it('normal mode on an empty buffer does not crash', () => {
    const v = new VimEngine();
    for (const k of ['h', 'j', 'k', 'l', 'w', 'b', 'e', '$', '0', 'G', 'x', 'p']) {
      expect(() => v.handleKey(key(k), buf('', 0))).not.toThrow();
    }
  });
});
