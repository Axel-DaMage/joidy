import { describe, it, expect } from 'vitest';
import { extractFrontmatter, getFileIcon, isNoteInFolder, buildTree } from './fileTree';
import type { Note } from '$lib/api';

const note = (over: Partial<Note>): Note => ({
  id: 1,
  title: 'n',
  content: '',
  source: 'manual',
  source_path: null,
  tags: [],
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  ...over,
});

describe('extractFrontmatter', () => {
  it('returns null fields for empty content', () => {
    expect(extractFrontmatter('')).toEqual({ icon: null, color: null, pack: null });
  });

  it('returns null fields for content without frontmatter', () => {
    expect(extractFrontmatter('# Hello\n\nJust a note')).toEqual({ icon: null, color: null, pack: null });
  });

  it('parses icon from frontmatter', () => {
    const result = extractFrontmatter('---\nicon: Star\niconColor: "#ff0000"\n---\n\nContent');
    expect(result).toMatchObject({ icon: 'Star', color: '"#ff0000"' });
  });

  it('parses iconPack from frontmatter', () => {
    const result = extractFrontmatter('---\nicon: Home\niconPack: phosphor\n---\n\nBody');
    expect(result).toMatchObject({ icon: 'Home', pack: 'phosphor' });
  });

  it('handles missing closing ---', () => {
    expect(extractFrontmatter('---\nicon: Star\n\nContent')).toEqual({ icon: null, color: null, pack: null });
  });

  it('handles empty frontmatter', () => {
    expect(extractFrontmatter('---\n---\n\nContent')).toEqual({ icon: null, color: null, pack: null });
  });
});

describe('getFileIcon', () => {
  it('returns File as default fallback', () => {
    expect(getFileIcon('Random Note', '')).toBe('File');
  });

  it('returns icon from frontmatter icon field in content', () => {
    expect(getFileIcon('Any', '---\nicon: Star\n---\n\nBody')).toBe('Star');
  });

  it('returns FileCode for content with code blocks', () => {
    expect(getFileIcon('Code', 'Some text\n```\ncode here\n```\nmore')).toBe('FileCode');
  });
});

// #1304 — folder delete used `source_path.includes(path)`, which also matched
// sibling folders (`foo` matched `foo2/x.md` and `a/foobar/y.md`), wiping
// notes outside the folder being deleted.
describe('isNoteInFolder — segment-boundary match (#1304)', () => {
  it('matches notes directly inside the folder', () => {
    expect(isNoteInFolder('foo/x.md', 'foo')).toBe(true);
    expect(isNoteInFolder('foo/sub/x.md', 'foo')).toBe(true);
  });

  it('does not match sibling folders sharing a prefix', () => {
    expect(isNoteInFolder('foo2/x.md', 'foo')).toBe(false);
    expect(isNoteInFolder('a/foobar/y.md', 'foo')).toBe(false);
  });

  it('does not match a same-named nested folder at a different path', () => {
    expect(isNoteInFolder('a/foo/y.md', 'foo')).toBe(false);
    expect(isNoteInFolder('a/foo/y.md', 'a/foo')).toBe(true);
  });

  it('normalizes the /vault/ prefix like buildTree', () => {
    expect(isNoteInFolder('/vault/foo/x.md', 'foo')).toBe(true);
    expect(isNoteInFolder('/vault/foo2/x.md', 'foo')).toBe(false);
  });

  it('matches exact path equality and rejects empty folder', () => {
    expect(isNoteInFolder('foo', 'foo')).toBe(true);
    expect(isNoteInFolder('foo/x.md', '')).toBe(false);
  });
});

// #1304 — tree children were keyed by title/stem, so two notes with the same
// title overwrote each other and only one rendered.
describe('buildTree — duplicate titles (#1304)', () => {
  it('keeps two joidy notes with the same title', () => {
    const tree = buildTree([note({ id: 1, title: 'Todo' }), note({ id: 2, title: 'Todo' })]);
    const joidy = tree.find((n) => n.name === '✦ joidy');
    expect(joidy).toBeTruthy();
    expect(joidy!.children).toHaveLength(2);
    expect(
      joidy!
        .children.map((c) => c.note?.id)
        .sort((a, b) => (a ?? 0) - (b ?? 0))
    ).toEqual([1, 2]);
    expect(joidy!.children.every((c) => c.name === 'Todo')).toBe(true);
  });

  it('keeps two vault notes sharing a stem inside one folder', () => {
    const tree = buildTree([
      note({ id: 3, title: 'Todo', source_path: 'a/Todo.md' }),
      note({ id: 4, title: 'Todo', source_path: 'a/Todo' }),
    ]);
    const a = tree.find((n) => n.name === 'a');
    expect(a).toBeTruthy();
    expect(a!.children).toHaveLength(2);
  });
});
