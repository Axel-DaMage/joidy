import { describe, it, expect } from 'vitest';
import { recomposeHiddenSlices } from './noteContent';

// #1304 — the textarea and the WYSIWYG editor operate on the stripped
// "visible" content; any edit result must re-attach the hidden slices
// (frontmatter block, `# Tags:` line) exactly like the input handler does,
// otherwise formatting offsets corrupt the text or the YAML is destroyed.
describe('recomposeHiddenSlices (#1304)', () => {
  const fm = '---\nicon: Star\n---';

  it('returns the visible text unchanged when nothing was hidden', () => {
    expect(recomposeHiddenSlices('Body text', {})).toBe('Body text');
  });

  it('re-attaches a hidden frontmatter block verbatim', () => {
    expect(recomposeHiddenSlices('Body text', { frontmatter: fm })).toBe(
      '---\nicon: Star\n---\n\nBody text'
    );
  });

  it('re-appends a hidden tags line', () => {
    expect(recomposeHiddenSlices('Body', { tagsLine: '# Tags: [[a]]' })).toBe(
      'Body\n\n# Tags: [[a]]'
    );
  });

  it('does not duplicate a tags line already present', () => {
    expect(recomposeHiddenSlices('Body\n# Tags: [[a]]', { tagsLine: '# Tags: [[a]]' })).toBe(
      'Body\n# Tags: [[a]]'
    );
  });

  it('re-attaches both slices when both were hidden', () => {
    expect(recomposeHiddenSlices('Body', { tagsLine: '# Tags: [[a]]', frontmatter: fm })).toBe(
      '---\nicon: Star\n---\n\nBody\n\n# Tags: [[a]]'
    );
  });
});
