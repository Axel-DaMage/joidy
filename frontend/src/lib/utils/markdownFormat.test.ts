import { describe, it, expect } from 'vitest';
import { isAllowedLinkUrl } from './markdownFormat';

describe('isAllowedLinkUrl — scheme allowlist (#1331)', () => {
  it('accepts https URLs', () => {
    expect(isAllowedLinkUrl('https://example.com')).toBe(true);
    expect(isAllowedLinkUrl('https://example.com/path?q=1#frag')).toBe(true);
  });

  it('accepts http URLs', () => {
    expect(isAllowedLinkUrl('http://example.com')).toBe(true);
  });

  it('accepts mailto URLs', () => {
    expect(isAllowedLinkUrl('mailto:user@example.com')).toBe(true);
  });

  it('accepts relative and anchor URLs', () => {
    expect(isAllowedLinkUrl('page.md')).toBe(true);
    expect(isAllowedLinkUrl('./notes/today.md')).toBe(true);
    expect(isAllowedLinkUrl('../up.md')).toBe(true);
    expect(isAllowedLinkUrl('/absolute/path')).toBe(true);
    expect(isAllowedLinkUrl('#section')).toBe(true);
  });

  it('rejects javascript: URLs', () => {
    expect(isAllowedLinkUrl('javascript:alert(1)')).toBe(false);
    expect(isAllowedLinkUrl('JaVaScRiPt:alert(1)')).toBe(false);
    expect(isAllowedLinkUrl('  javascript:alert(1)  ')).toBe(false);
  });

  it('rejects obfuscated javascript: URLs', () => {
    // WHATWG URL parsing strips ASCII tab/newline before checking the scheme.
    expect(isAllowedLinkUrl('java\tscript:alert(1)')).toBe(false);
    expect(isAllowedLinkUrl('java\nscript:alert(1)')).toBe(false);
  });

  it('rejects data:, vbscript:, file: and other schemes', () => {
    expect(isAllowedLinkUrl('data:text/html,<script>alert(1)</script>')).toBe(false);
    expect(isAllowedLinkUrl('vbscript:msgbox(1)')).toBe(false);
    expect(isAllowedLinkUrl('file:///etc/passwd')).toBe(false);
    expect(isAllowedLinkUrl('ftp://example.com/file')).toBe(false);
    expect(isAllowedLinkUrl('tel:+1234567890')).toBe(false);
  });

  it('rejects unknown schemes', () => {
    expect(isAllowedLinkUrl('evilscheme:payload')).toBe(false);
  });

  it('rejects empty and whitespace-only input', () => {
    expect(isAllowedLinkUrl('')).toBe(false);
    expect(isAllowedLinkUrl('   ')).toBe(false);
  });

  it('rejects URLs that fail to parse', () => {
    expect(isAllowedLinkUrl('https://')).toBe(false);
  });
});
