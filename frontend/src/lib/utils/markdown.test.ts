import { describe, it, expect } from 'vitest';
import { renderMarkdown } from './markdown';

describe('renderMarkdown — basic markdown', () => {
  it('returns placeholder for empty input', () => {
    const result = renderMarkdown('');
    expect(result).toContain('Escribe algo');
    expect(result).toContain('font-style:italic');
  });

  it('returns placeholder for whitespace-only input', () => {
    const result = renderMarkdown('   \n\n  ');
    expect(result).toContain('Escribe algo');
  });

  it('renders headings', () => {
    const result = renderMarkdown('# Title');
    expect(result).toContain('<h1>');
    expect(result).toContain('Title');
  });

  it('renders bold and italic', () => {
    const result = renderMarkdown('**bold** and *italic*');
    expect(result).toContain('<strong>');
    expect(result).toContain('<em>');
  });

  it('renders unordered lists', () => {
    const result = renderMarkdown('- item 1\n- item 2');
    expect(result).toContain('<ul>');
    expect(result).toContain('<li>');
    expect(result).toContain('item 1');
    expect(result).toContain('item 2');
  });

  it('renders ordered lists', () => {
    const result = renderMarkdown('1. first\n2. second');
    expect(result).toContain('<ol>');
    expect(result).toContain('first');
    expect(result).toContain('second');
  });

  it('renders blockquotes', () => {
    const result = renderMarkdown('> quoted text');
    expect(result).toContain('<blockquote>');
    expect(result).toContain('quoted text');
  });

  it('renders links', () => {
    const result = renderMarkdown('[example](https://example.com)');
    expect(result).toContain('<a');
    expect(result).toContain('href="https://example.com"');
    expect(result).toContain('example');
  });

  it('renders code blocks with highlighting', () => {
    const result = renderMarkdown('```python\nprint("hello")\n```');
    expect(result).toContain('<pre>');
    expect(result).toContain('<code');
    expect(result).toContain('hljs');
  });

  it('renders inline code', () => {
    const result = renderMarkdown('use `npm` to install');
    expect(result).toContain('<code>');
    expect(result).toContain('npm');
  });

  it('renders tables (GFM)', () => {
    const result = renderMarkdown('| A | B |\n|---|---|\n| 1 | 2 |');
    expect(result).toContain('<table>');
    expect(result).toContain('<th>');
    expect(result).toContain('<td>');
  });

  it('renders horizontal rule', () => {
    const result = renderMarkdown('---\n');
    expect(result).toContain('<hr');
  });
});

describe('renderMarkdown — wikilinks (Obsidian)', () => {
  it('converts [[title]] to wikilink span', () => {
    const result = renderMarkdown('See [[my note]] for details');
    expect(result).toContain('class="wikilink"');
    expect(result).toContain('data-title="my note"');
    expect(result).toContain('my note');
  });

  it('converts [[title|alias]] using alias as display text', () => {
    const result = renderMarkdown('See [[my note|display text]]');
    expect(result).toContain('data-title="my note"');
    expect(result).toContain('display text');
    expect(result).not.toContain('>my note<');
  });

  it('handles multiple wikilinks in one line', () => {
    const result = renderMarkdown('[[a]] and [[b]]');
    expect(result).toContain('data-title="a"');
    expect(result).toContain('data-title="b"');
  });
});

describe('renderMarkdown — sanitization (DOMPurify)', () => {
  it('strips script tags', () => {
    const result = renderMarkdown('<script>alert("xss")</script>');
    expect(result).not.toContain('<script>');
    expect(result).not.toContain('alert');
  });

  it('strips iframe tags', () => {
    const result = renderMarkdown('<iframe src="evil.com"></iframe>');
    expect(result).not.toContain('<iframe');
  });

  it('strips onclick handlers', () => {
    const result = renderMarkdown('<a href="#" onclick="alert(1)">click</a>');
    expect(result).not.toContain('onclick');
  });

  it('strips style attributes', () => {
    const result = renderMarkdown('<p style="color:red">text</p>');
    expect(result).not.toContain('style=');
  });

  it('preserves safe links', () => {
    const result = renderMarkdown('[safe](https://example.com)');
    expect(result).toContain('href="https://example.com"');
  });

  it('preserves img tags with src and alt', () => {
    const result = renderMarkdown('![alt text](https://example.com/img.png)');
    expect(result).toContain('<img');
    expect(result).toContain('src="https://example.com/img.png"');
    expect(result).toContain('alt="alt text"');
  });
});

describe('renderMarkdown — hideTagsLine option', () => {
  it('removes # Tags: line when hideTagsLine and hasTags', () => {
    const md = '# Tags: [[tag1]] [[tag2]]\n\nSome content here';
    const result = renderMarkdown(md, { hideTagsLine: true, hasTags: true });
    expect(result).not.toContain('Tags:');
    expect(result).toContain('Some content here');
  });

  it('removes # tags: line (case insensitive)', () => {
    const md = '# tags: [[tag1]]\n\nContent';
    const result = renderMarkdown(md, { hideTagsLine: true, hasTags: true });
    expect(result).not.toContain('tags:');
    expect(result).toContain('Content');
  });

  it('keeps # Tags: line when hideTagsLine is false', () => {
    const md = '# Tags: [[tag1]]\n\nContent';
    const result = renderMarkdown(md, { hideTagsLine: false, hasTags: true });
    expect(result).toContain('Tags:');
  });

  it('keeps # Tags: line when hasTags is false', () => {
    const md = '# Tags: [[tag1]]\n\nContent';
    const result = renderMarkdown(md, { hideTagsLine: true, hasTags: false });
    expect(result).toContain('Tags:');
  });
});
