import { describe, it, expect } from 'vitest';
import { extractFrontmatter, getFileIcon } from './fileTree';

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
