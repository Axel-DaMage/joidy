import { describe, it, expect } from 'vitest';
import {
  sanitizeEmailHtml,
  parseAddress,
  senderLabel,
  formatEmailDate,
  formatBytes,
  isGmailAuthError,
  base64ToBlob,
  fileToBase64Payload,
} from './gmail';

describe('sanitizeEmailHtml', () => {
  it('returns empty string for empty input', () => {
    expect(sanitizeEmailHtml(null)).toBe('');
    expect(sanitizeEmailHtml(undefined)).toBe('');
    expect(sanitizeEmailHtml('')).toBe('');
  });

  it('strips <script> and event handlers', () => {
    const out = sanitizeEmailHtml(
      '<p>Hola</p><script>alert("xss")</script><img src="x" onerror="alert(1)">',
    );
    expect(out).not.toContain('<script');
    expect(out).not.toContain('onerror');
    expect(out).not.toContain('alert(');
    expect(out).toContain('<p>Hola</p>');
  });

  it('neutralizes javascript: URLs in href', () => {
    const out = sanitizeEmailHtml('<a href="javascript:alert(1)">click</a>');
    expect(out).not.toContain('javascript:');
  });

  it('keeps safe formatting and table markup', () => {
    const out = sanitizeEmailHtml(
      '<table><tr><td><strong>bold</strong> <em>it</em></td></tr></table><ul><li>one</li></ul>',
    );
    expect(out).toContain('<table>');
    expect(out).toContain('<strong>bold</strong>');
    expect(out).toContain('<li>one</li>');
  });

  it('drops style/class attributes (UI-redress hardening)', () => {
    const out = sanitizeEmailHtml(
      '<div style="position:fixed;inset:0" class="evil">x</div>',
    );
    expect(out).not.toContain('style=');
    expect(out).not.toContain('class=');
    expect(out).toContain('x');
  });

  it('forces rel="noopener noreferrer" on target=_blank links', () => {
    const out = sanitizeEmailHtml(
      '<a href="https://example.com" target="_blank">x</a>',
    );
    expect(out).toContain('target="_blank"');
    expect(out).toContain('rel="noopener noreferrer"');
  });

  it('allows https images but strips iframes', () => {
    const out = sanitizeEmailHtml(
      '<img src="https://example.com/p.png" alt="p"><iframe src="https://evil.example"></iframe>',
    );
    expect(out).toContain('<img');
    expect(out).not.toContain('<iframe');
  });
});

describe('parseAddress', () => {
  it('parses "Name" <email> form', () => {
    expect(parseAddress('"Doe, John" <john@example.com>')).toEqual({
      name: 'Doe, John',
      email: 'john@example.com',
    });
  });

  it('parses bare email', () => {
    expect(parseAddress('jane@example.com')).toEqual({
      name: '',
      email: 'jane@example.com',
    });
  });

  it('parses display name without address', () => {
    expect(parseAddress('Jane Doe')).toEqual({ name: 'Jane Doe', email: '' });
  });

  it('handles empty input', () => {
    expect(parseAddress(null)).toEqual({ name: '', email: '' });
    expect(parseAddress('  ')).toEqual({ name: '', email: '' });
  });
});

describe('senderLabel', () => {
  it('prefers display name over address', () => {
    expect(senderLabel({ from: '"Ana" <ana@example.com>' })).toBe('Ana');
  });

  it('falls back to email when no display name', () => {
    expect(senderLabel({ from: 'ana@example.com' })).toBe('ana@example.com');
  });

  it('returns empty for missing headers', () => {
    expect(senderLabel({})).toBe('');
    expect(senderLabel(null)).toBe('');
  });
});

describe('formatEmailDate', () => {
  it('returns empty for missing/invalid input', () => {
    expect(formatEmailDate(null)).toBe('');
    expect(formatEmailDate('not-a-date')).toBe('');
  });

  it('formats a valid ISO date', () => {
    const out = formatEmailDate('2024-01-15T10:30:00Z');
    expect(out).toBeTruthy();
    expect(out).toContain('15');
  });
});

describe('formatBytes', () => {
  it('handles null/invalid', () => {
    expect(formatBytes(null)).toBe('');
    expect(formatBytes(undefined)).toBe('');
    expect(formatBytes(-1)).toBe('');
  });

  it('formats B/KB/MB', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(2048)).toBe('2.0 KB');
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB');
  });
});

describe('isGmailAuthError', () => {
  it('detects 401/403 api errors', () => {
    expect(
      isGmailAuthError(
        new Error('API GET /integrations/gmail/messages → 403: {}'),
      ),
    ).toBe(true);
    expect(isGmailAuthError(new Error('API POST /x → 401: {}'))).toBe(true);
  });

  it('rejects other statuses and non-errors', () => {
    expect(isGmailAuthError(new Error('API GET /x → 500: {}'))).toBe(false);
    expect(isGmailAuthError(new Error('API GET /x → 429: {}'))).toBe(false);
    expect(isGmailAuthError('random string')).toBe(false);
    expect(isGmailAuthError(null)).toBe(false);
  });
});

describe('base64ToBlob', () => {
  it('decodes base64 into a typed blob', () => {
    const blob = base64ToBlob(btoa('hello'), 'text/plain');
    expect(blob.type).toBe('text/plain');
    expect(blob.size).toBe(5);
  });
});

describe('fileToBase64Payload', () => {
  it('encodes a File as base64 payload', async () => {
    const file = new File(['hola'], 'nota.txt', { type: 'text/plain' });
    const payload = await fileToBase64Payload(file);
    expect(payload.filename).toBe('nota.txt');
    expect(payload.content_type).toBe('text/plain');
    expect(atob(payload.data_base64)).toBe('hola');
  });
});
