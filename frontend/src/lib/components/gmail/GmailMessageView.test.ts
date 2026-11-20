import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, cleanup } from '@testing-library/svelte';
import type { GmailMessage } from '$lib/api';
import GmailMessageView from './GmailMessageView.svelte';

// downloadGmailAttachment pulls the api client — stub the module so the
// component test never touches the network.
vi.mock('$lib/utils/gmail', async (importOriginal) => {
  const actual = await importOriginal<typeof import('$lib/utils/gmail')>();
  return {
    ...actual,
    downloadGmailAttachment: vi.fn().mockResolvedValue(undefined),
  };
});

function makeMessage(overrides: Partial<GmailMessage> = {}): GmailMessage {
  return {
    id: 'msg-1',
    thread_id: 'thread-1',
    label_ids: ['INBOX'],
    snippet: 'preview',
    internal_date: '2024-01-15T10:30:00Z',
    size_estimate: 1024,
    history_id: 'h1',
    headers: {
      from: '"Ana" <ana@example.com>',
      to: 'me@example.com',
      subject: 'Hola',
      date: 'Mon, 15 Jan 2024 10:30:00 +0000',
    },
    body_text: null,
    body_html: null,
    body_truncated: false,
    attachments: [],
    ...overrides,
  };
}

function renderView(message: GmailMessage) {
  return render(GmailMessageView, {
    message,
    canModify: true,
    canSend: true,
    loading: false,
    onBack: () => {},
    onArchive: () => {},
    onTrash: () => {},
    onUntrash: () => {},
    onToggleRead: () => {},
    onReply: () => {},
  });
}

describe('GmailMessageView', () => {
  beforeEach(() => cleanup());

  it('renders headers and a plain-text body', () => {
    const { getByText, container } = renderView(
      makeMessage({ body_text: 'Hola mundo', body_html: null }),
    );
    expect(getByText('Hola')).toBeTruthy();
    // from header '"Ana" <ana@example.com>' renders the display name.
    expect(getByText('Ana')).toBeTruthy();
    expect(getByText('me@example.com')).toBeTruthy();
    expect(container.querySelector('.gmail-text')?.textContent).toContain(
      'Hola mundo',
    );
  });

  it('sanitizes hostile body_html before rendering (XSS)', () => {
    const { container } = renderView(
      makeMessage({
        body_html:
          '<p>safe</p><script>window.__pwned = true</script>' +
          '<img src="x" onerror="window.__pwned = true">' +
          '<a href="javascript:window.__pwned=1">bad</a>',
      }),
    );
    expect(container.querySelector('script')).toBeNull();
    expect(container.innerHTML).not.toContain('onerror');
    expect(container.innerHTML).not.toContain('javascript:');
    expect(container.querySelector('.gmail-body')?.innerHTML).toContain('safe');
  });

  it('lists attachments with download buttons', () => {
    const { getByText } = renderView(
      makeMessage({
        attachments: [
          {
            attachment_id: 'att-1',
            filename: 'factura.pdf',
            mime_type: 'application/pdf',
            size: 2048,
            part_id: '1',
          },
        ],
      }),
    );
    expect(getByText('factura.pdf')).toBeTruthy();
    expect(getByText('2.0 KB')).toBeTruthy();
  });
});
