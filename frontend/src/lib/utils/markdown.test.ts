import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock $app/env so `browser` is true (jsdom): getToken() reads localStorage
// and api.ts resolves BASE to http://localhost:8000.
vi.mock('$app/env', () => ({ browser: true, dev: false }));

import { authorizeUploadUrls, renderMarkdown, stripUploadAuth } from './markdown';

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

  it('escapes HTML injected via the alias (#1317)', () => {
    const result = renderMarkdown('See [[x|<img src="https://evil/t">]]');
    // The alias must become an escaped literal — `<img>` is on the DOMPurify
    // allowlist, so unescaped interpolation would survive sanitization.
    expect(result).toContain('&lt;img');
    expect(result).toContain('class="wikilink"');
    const doc = new DOMParser().parseFromString(result, 'text/html');
    expect(doc.querySelector('img')).toBeNull();
    // The alias must stay literal text — marked must not autolink the escaped
    // URL into an injected anchor either.
    expect(doc.querySelector('a')).toBeNull();
    expect(doc.querySelector('.wikilink')?.textContent).toBe('<img src="https://evil/t">');
  });

  it('escapes quotes that would break out of data-title (#1317)', () => {
    const result = renderMarkdown('[[a"><img src=x>]]');
    const doc = new DOMParser().parseFromString(result, 'text/html');
    expect(doc.querySelector('img')).toBeNull();
    expect(doc.querySelector('.wikilink')?.getAttribute('data-title')).toBe('a"><img src=x>');
  });

  it('does not render wikilink spans as markup before sanitization', () => {
    const result = renderMarkdown('[[x|<script>alert(1)</script>]]');
    expect(result).not.toContain('<script>');
    expect(result).toContain('&lt;script&gt;');
  });

  it('marks [[Contact:Name]] as a contact wikilink with the bare name (#43)', () => {
    const result = renderMarkdown('Call [[Contact:Ada Lovelace]] tomorrow');
    expect(result).toContain('wikilink-contact');
    // data-title carries the stripped contact name for /contactos?q= routing.
    expect(result).toContain('data-title="Ada Lovelace"');
    // Visible text stays exactly what the author wrote.
    expect(result).toContain('Contact:Ada Lovelace');
  });

  it('supports alias and case-insensitive prefix on contact links', () => {
    const result = renderMarkdown('See [[contact:grace|Grace H.]]');
    expect(result).toContain('wikilink-contact');
    expect(result).toContain('data-title="grace"');
    expect(result).toContain('Grace H.');
  });

  it('keeps [[Contact]] (no colon) as a regular note wikilink', () => {
    const result = renderMarkdown('See [[Contact]]');
    expect(result).toContain('class="wikilink"');
    expect(result).not.toContain('wikilink-contact');
    expect(result).toContain('data-title="Contact"');
  });

  it('keeps [[Contact:]] (empty name) as a regular note wikilink', () => {
    const result = renderMarkdown('See [[Contact:]]');
    expect(result).not.toContain('wikilink-contact');
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

  it('forces rel="noopener noreferrer" on target="_blank" links (#1331)', () => {
    const result = renderMarkdown('<a href="https://example.com" target="_blank">click</a>');
    expect(result).toContain('target="_blank"');
    expect(result).toContain('rel="noopener noreferrer"');
  });

  it('overwrites a malicious rel="opener" on target="_blank" links (#1331)', () => {
    const result = renderMarkdown(
      '<a href="https://example.com" target="_blank" rel="opener">click</a>'
    );
    expect(result).toContain('rel="noopener noreferrer"');
    expect(result).not.toContain('rel="opener"');
  });

  it('strips rel from links without target (#1331)', () => {
    const result = renderMarkdown('<a href="https://example.com" rel="opener">click</a>');
    expect(result).not.toContain('rel=');
    expect(result).not.toContain('opener');
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

describe('authorizeUploadUrls — /uploads JWT injection (#1279)', () => {
  const API = 'http://localhost:8000';

  beforeEach(() => {
    localStorage.clear();
  });

  it('appends the session token to API-origin upload img src', () => {
    localStorage.setItem('joidy_session', JSON.stringify({ token: 'jwt-abc' }));
    const html = `<img src="${API}/uploads/pic.png" alt="pic">`;
    expect(authorizeUploadUrls(html)).toBe(
      `<img src="${API}/uploads/pic.png?token=jwt-abc" alt="pic">`
    );
  });

  it('appends the token to root-relative upload href', () => {
    localStorage.setItem('joidy_session', JSON.stringify({ token: 'jwt-abc' }));
    const html = '<a href="/uploads/doc.pdf">doc</a>';
    expect(authorizeUploadUrls(html)).toBe('<a href="/uploads/doc.pdf?token=jwt-abc">doc</a>');
  });

  it('does not leak the token to foreign /uploads/ hosts', () => {
    localStorage.setItem('joidy_session', JSON.stringify({ token: 'jwt-abc' }));
    const html = '<img src="https://evil.example/uploads/x.png">';
    expect(authorizeUploadUrls(html)).toBe(html);
  });

  it('does not double-append when a token is already present', () => {
    localStorage.setItem('joidy_session', JSON.stringify({ token: 'jwt-new' }));
    const html = '<img src="/uploads/x.png?token=jwt-old">';
    expect(authorizeUploadUrls(html)).toBe(html);
  });

  it('no-ops without a session token', () => {
    const html = '<img src="/uploads/x.png">';
    expect(authorizeUploadUrls(html)).toBe(html);
  });

  it('renderMarkdown injects the token into stored upload embeds', () => {
    localStorage.setItem('joidy_session', JSON.stringify({ token: 'jwt-abc' }));
    const out = renderMarkdown(`![pic](${API}/uploads/pic.png)`);
    expect(out).toContain('?token=jwt-abc');
  });
});

describe('stripUploadAuth — keeps JWT out of saved markdown (#1279)', () => {
  it('removes ?token= from upload URLs', () => {
    expect(stripUploadAuth('<img src="http://h:8000/uploads/x.png?token=T">')).toBe(
      '<img src="http://h:8000/uploads/x.png">'
    );
  });

  it('removes &token= and &amp;token= mid-query', () => {
    expect(stripUploadAuth('<a href="/uploads/x?a=1&token=T">f</a>')).toBe(
      '<a href="/uploads/x?a=1">f</a>'
    );
    expect(stripUploadAuth('<img src="/uploads/x?a=1&amp;token=T">')).toBe(
      '<img src="/uploads/x?a=1">'
    );
  });

  it('leaves non-upload token params untouched', () => {
    const html = '<a href="https://x.test/page?token=keep">l</a>';
    expect(stripUploadAuth(html)).toBe(html);
  });
});
