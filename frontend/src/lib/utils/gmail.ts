/**
 * Gmail client helpers (#42): inbound-HTML sanitization, address parsing,
 * date/size formatting and base64 attachment plumbing for the /gmail page.
 *
 * SECURITY: `GmailMessage.body_html` is RAW HTML produced by remote senders —
 * it must pass through {@link sanitizeEmailHtml} (DOMPurify) before any
 * `{@html}` render. Never interpolate it directly.
 */
import DOMPurify from 'dompurify';
import { api, type GmailAttachmentMeta, type GmailMessage } from '$lib/api';

// ── HTML sanitization ────────────────────────────────────────────────────────

/**
 * Email-safe tag allowlist. Covers the structure real HTML mail needs
 * (tables, lists, inline formatting, images) while excluding active content
 * (`script`, `iframe`, `object`, `embed`, `form`, `style`, `svg`, `math`).
 */
const EMAIL_ALLOWED_TAGS = [
  'a',
  'abbr',
  'b',
  'blockquote',
  'br',
  'caption',
  'center',
  'cite',
  'code',
  'col',
  'colgroup',
  'dd',
  'del',
  'details',
  'dfn',
  'div',
  'dl',
  'dt',
  'em',
  'figcaption',
  'figure',
  'font',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'hr',
  'i',
  'img',
  'ins',
  'kbd',
  'li',
  'mark',
  'ol',
  'p',
  'pre',
  'q',
  's',
  'samp',
  'small',
  'span',
  'strike',
  'strong',
  'sub',
  'summary',
  'sup',
  'table',
  'tbody',
  'td',
  'tfoot',
  'th',
  'thead',
  'time',
  'tr',
  'u',
  'ul',
  'var',
  'wbr',
];

/**
 * Attribute allowlist — deliberately excludes `style`, `class` and `id`:
 * sender-controlled CSS enables UI-redress (fixed overlays covering the app)
 * and class collisions with app styles, with no sanitization safety net for
 * CSS contents. Presentational attributes (width/align/bgcolor/…) keep
 * table-based mail readable.
 */
const EMAIL_ALLOWED_ATTR = [
  'href',
  'src',
  'alt',
  'title',
  'width',
  'height',
  'align',
  'valign',
  'colspan',
  'rowspan',
  'bgcolor',
  'color',
  'face',
  'size',
  'border',
  'cellpadding',
  'cellspacing',
  'cite',
  'datetime',
  'dir',
  'lang',
  'start',
  'type',
  'reversed',
  'span',
  'scope',
  'abbr',
  'headers',
  'target',
];

let relHookRegistered = false;

/**
 * Sanitize inbound email HTML for `{@html}` rendering.
 *
 * - Per-call config keeps this independent of the global DOMPurify profile
 *   used by `renderMarkdown` (markdown.ts) — neither clobbers the other.
 * - A global `afterSanitizeAttributes` hook forces `rel="noopener noreferrer"`
 *   on `target` links (reverse-tabnabbing guard, same rule as markdown.ts).
 *   Idempotent if markdown.ts's identical hook is also registered.
 * - Returns '' without a DOM: dompurify@3's `sanitize` is an unsanitized
 *   passthrough under SSR, so emitting it would defeat the point (#1317).
 */
export function sanitizeEmailHtml(html: string | null | undefined): string {
  if (!html) return '';
  if (typeof window === 'undefined') return '';
  if (!relHookRegistered) {
    relHookRegistered = true;
    DOMPurify.addHook('afterSanitizeAttributes', (node) => {
      if (node.localName === 'a' && node.hasAttribute('target')) {
        node.setAttribute('rel', 'noopener noreferrer');
      }
    });
  }
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: EMAIL_ALLOWED_TAGS,
    ALLOWED_ATTR: EMAIL_ALLOWED_ATTR,
  });
}

// ── Addresses ────────────────────────────────────────────────────────────────

export interface ParsedAddress {
  name: string;
  email: string;
}

/**
 * Parse a mailbox header value (`"Name" <a@b.c>`, `a@b.c`, or a bare display
 * name). For address lists only the first mailbox is returned — callers
 * needing all recipients should display the raw header instead.
 *
 * NOTE: the display name may itself contain commas inside quotes
 * (`"Doe, John" <john@x.com>`), so the first `<addr-spec>` group is located
 * directly instead of splitting on ','.
 */
export function parseAddress(header: string | null | undefined): ParsedAddress {
  const raw = (header || '').trim();
  if (!raw) return { name: '', email: '' };

  const angled = raw.match(/<([^<>\s]+@[^<>\s]+)>/);
  if (angled) {
    const name = raw
      .slice(0, angled.index ?? 0)
      .trim()
      .replace(/^,+|,+$/g, '')
      .replace(/^"+|"+$/g, '')
      .trim();
    return { name, email: angled[1].trim() };
  }
  const bare = raw.match(/[^\s@,]+@[^\s@,]+/);
  if (bare) return { name: '', email: bare[0] };
  return { name: raw, email: '' };
}

/** Human label for a message sender: display name, else the address. */
export function senderLabel(
  headers: Record<string, string> | null | undefined,
): string {
  const from = headers?.from;
  if (!from) return '';
  const { name, email } = parseAddress(from);
  return name || email || from;
}

// ── Formatting ───────────────────────────────────────────────────────────────

const timeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit',
  minute: '2-digit',
});
const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
});

/**
 * Inbox-style timestamp: time-only for today's mail, day+month+time for
 * older items. Returns '' for missing/unparseable input.
 */
export function formatEmailDate(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toDateString() === new Date().toDateString()
    ? timeFormatter.format(date)
    : dateTimeFormatter.format(date);
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || !Number.isFinite(bytes) || bytes < 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Errors ───────────────────────────────────────────────────────────────────

/**
 * True when an api.gmail call failed with 401/403 — the Google grant is
 * missing, expired or under-scoped and the user must reconnect in Settings.
 * The `req()` error format is `API <METHOD> <path> → <status>: <body>`.
 */
export function isGmailAuthError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '');
  return /→\s*40[13]\b/.test(message);
}

// ── Attachments ──────────────────────────────────────────────────────────────

/** Standard base64 → Blob (attachment payloads arrive as base64 JSON). */
export function base64ToBlob(dataBase64: string, mimeType: string): Blob {
  const binary = atob(dataBase64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type: mimeType || 'application/octet-stream' });
}

function triggerBrowserDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename || 'attachment';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Revoke after the click had a chance to start the download.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Download one message attachment: fetch the base64 payload from the API and
 * save it via a synthetic anchor click. Throws on API failure — callers
 * surface the error themselves.
 */
export async function downloadGmailAttachment(
  message: GmailMessage,
  attachment: GmailAttachmentMeta,
): Promise<void> {
  if (!message.id || !attachment.attachment_id) {
    throw new Error('Attachment reference missing');
  }
  const data = await api.gmail.attachment(message.id, attachment.attachment_id);
  const blob = base64ToBlob(
    data.data_base64,
    attachment.mime_type || 'application/octet-stream',
  );
  triggerBrowserDownload(
    blob,
    attachment.filename || `attachment-${attachment.attachment_id}`,
  );
}

export interface OutgoingAttachmentPayload {
  filename: string;
  content_type: string;
  data_base64: string;
}

/** File → {filename, content_type, data_base64} for POST /messages/send. */
export function fileToBase64Payload(
  file: File,
): Promise<OutgoingAttachmentPayload> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || '');
      const comma = result.indexOf(',');
      resolve({
        filename: file.name || 'attachment',
        content_type: file.type || 'application/octet-stream',
        data_base64: comma >= 0 ? result.slice(comma + 1) : result,
      });
    };
    reader.onerror = () =>
      reject(reader.error ?? new Error('Could not read file'));
    reader.readAsDataURL(file);
  });
}
