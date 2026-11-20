import { describe, it, expect } from 'vitest';
import { exportToHTML, exportToMarkdown } from './export';
import type { Note } from '$lib/api';

function makeNote(overrides: Partial<Note> = {}): Note {
  return {
    id: 1,
    title: 'My note',
    content: 'Some *content*',
    source: 'manual',
    source_path: null,
    tags: [],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    ...overrides,
  };
}

describe('exportToHTML — escaping (#1317)', () => {
  it('escapes the note title in both <title> and <h1>', () => {
    const html = exportToHTML(makeNote({ title: '<img src=x onerror=alert(1)>' }));
    expect(html).not.toContain('<img');
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;');
  });

  it('escapes tags and source_path', () => {
    const html = exportToHTML(
      makeNote({
        tags: ['<b>evil</b>'],
        source_path: '"><script>alert(1)</script>',
      })
    );
    expect(html).not.toContain('<b>evil</b>');
    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;b&gt;evil&lt;/b&gt;');
  });

  it('renders content through the sanitized markdown pipeline', () => {
    const html = exportToHTML(
      makeNote({ content: 'Hello **world**\n\n<script>alert(1)</script>' })
    );
    expect(html).toContain('<strong>world</strong>');
    expect(html).not.toContain('<script>');
  });

  it('keeps the content block empty for an empty note', () => {
    const html = exportToHTML(makeNote({ content: '   ' }));
    expect(html).toContain('<div class="content"></div>');
  });
});

describe('exportToMarkdown', () => {
  it('includes title, tags, content and source path', () => {
    const md = exportToMarkdown(
      makeNote({ title: 'T', tags: ['a', 'b'], content: 'body', source_path: 'vault/t.md' })
    );
    expect(md).toContain('# T');
    expect(md).toContain('[[a]]');
    expect(md).toContain('body');
    expect(md).toContain('vault/t.md');
  });
});
