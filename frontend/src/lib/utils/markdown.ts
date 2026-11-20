/**
 * Markdown rendering utility extracted from NoteEditor for testability (#369).
 *
 * Converts markdown → HTML via `marked` (GFM + syntax highlighting via
 * highlight.js), pre-processes Obsidian wikilinks, and sanitizes the output
 * with DOMPurify.
 */
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js';
import { BASE } from '$lib/api';
import { getToken } from '$lib/stores/session';

// Configure marked with GFM and syntax highlighting via highlight.js
const renderer = new marked.Renderer();
renderer.code = ({ text, lang }) => {
  const language = lang && hljs.getLanguage(lang) ? lang : '';
  let highlighted: string;
  try {
    highlighted = language
      ? hljs.highlight(text, { language }).value
      : hljs.highlightAuto(text).value;
  } catch {
    highlighted = text;
  }
  return `<pre><code class="hljs language-${language || 'auto'}">${highlighted}</code></pre>`;
};
marked.use({ gfm: true, breaks: true, renderer });

// Configure DOMPurify for safe markdown rendering.
// NOTE: `rel` is intentionally NOT in ALLOWED_ATTR — a rendered note could
// otherwise carry `target="_blank" rel="opener"` (reverse tabnabbing). Instead
// the hook below forces a safe `rel` on every anchor that sets `target`.
DOMPurify.setConfig({
  ALLOWED_TAGS: [
    'p',
    'br',
    'strong',
    'em',
    'a',
    'ul',
    'ol',
    'li',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'pre',
    'code',
    'blockquote',
    'table',
    'thead',
    'tbody',
    'tr',
    'th',
    'td',
    'span',
    'div',
    'hr',
    'img',
    'del',
    'ins',
    'sup',
    'sub',
  ],
  ALLOWED_ATTR: ['href', 'target', 'src', 'alt', 'class', 'data-title'],
});

// After attribute sanitization, force `rel="noopener noreferrer"` on any
// anchor that opens/navigates a browsing context via `target`, so a crafted
// `rel="opener"` can never retain `window.opener` (reverse tabnabbing).
// `localName` matches both HTML (`<A>`) and SVG (`<a>`) anchors.
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.localName === 'a' && node.hasAttribute('target')) {
    node.setAttribute('rel', 'noopener noreferrer');
  }
});

/**
 * Pre-process Obsidian wikilinks (`[[title]]` or `[[title|alias]]`) into HTML
 * spans before marked runs, since marked doesn't know about `[[links]]`.
 */
function preprocessWikilinks(md: string): string {
  return md.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (_match, title, alias) => {
    const display = alias || title;
    return `<span class="wikilink" data-title="${title.trim()}">${display}</span>`;
  });
}

/**
 * `/uploads/` is auth-gated (#1279): the API requires a valid JWT as an
 * `Authorization: Bearer` header or a `?token=` query param (see
 * SafeStaticFiles in api/main.py — same pattern as the `/ws` endpoint).
 * `<img>`/`<a>` elements rendered from markdown cannot send headers, so the
 * session token is appended to upload URLs at render time; stored markdown
 * keeps clean, token-free URLs.
 *
 * Only URLs on our own API origin (or root-relative `/uploads/...`) are
 * rewritten — appending the JWT to a foreign `/uploads/` path would leak it
 * to that host.
 */
const UPLOADS_URL_PATTERN = new RegExp(
  `(src|href)="((?:${BASE.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})?/uploads/[^"]*)"`,
  'g'
);

/**
 * Append the session JWT as `?token=` to `/uploads/` src/href URLs in a
 * rendered-HTML string. No-op when there is no session token (e.g. SSR or
 * logged out — auth is also bypassed in dev without AUTH_PASSWORD).
 */
export function authorizeUploadUrls(html: string): string {
  const token = getToken();
  if (!token) return html;
  return html.replace(UPLOADS_URL_PATTERN, (match, attr: string, url: string) => {
    if (/[?&]token=/.test(url)) return match;
    const sep = url.includes('?') ? '&' : '?';
    return `${attr}="${url}${sep}token=${encodeURIComponent(token)}"`;
  });
}

/**
 * Inverse of {@link authorizeUploadUrls}: strip injected `?token=` params
 * from `/uploads/` URLs in rendered HTML. WysiwygEditor runs this before
 * serializing back to markdown so the JWT is never persisted into note
 * content or synced to the vault.
 */
export function stripUploadAuth(html: string): string {
  return html
    .replace(/(\/uploads\/[^"'\s?]+)\?token=[^"'\s&]*/g, '$1')
    .replace(/(\/uploads\/[^"'\s]*?)(?:&|&amp;)token=[^"'\s&]*/g, '$1');
}

/**
 * Render markdown to sanitized HTML.
 *
 * @param md        - Raw markdown string
 * @param options   - Optional flags
 * @param options.hideTagsLine - Remove `# Tags: ...` lines before rendering
 * @param options.hasTags      - Whether tags exist (only strips tags line if true)
 */
export function renderMarkdown(
  md: string,
  options: { hideTagsLine?: boolean; hasTags?: boolean } = {}
): string {
  if (!md.trim()) {
    return '<p style="color:var(--text-muted);font-style:italic;">Escribe algo para ver el preview...</p>';
  }

  let preprocessed = md;
  if (options.hideTagsLine && options.hasTags) {
    preprocessed = preprocessed.replace(/^#\s*Tags?:\s*.*$/gim, '');
  }

  preprocessed = preprocessWikilinks(preprocessed);

  return authorizeUploadUrls(DOMPurify.sanitize(String(marked.parse(preprocessed))));
}
