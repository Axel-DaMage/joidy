/**
 * Markdown rendering utility extracted from NoteEditor for testability (#369).
 *
 * Converts markdown → HTML via `marked` (GFM + syntax highlighting via
 * highlight.js), pre-processes Obsidian wikilinks, and sanitizes the output
 * with DOMPurify.
 */
import { Marked, Renderer } from 'marked';
import DOMPurify from 'dompurify';
// highlight.js/lib/core + an allowlist: the default `highlight.js` entry
// bundles all ~190 language grammars (~900 kB) into the markdown chunk (#1311).
import hljs from 'highlight.js/lib/core';
import hlBash from 'highlight.js/lib/languages/bash';
import hlC from 'highlight.js/lib/languages/c';
import hlCpp from 'highlight.js/lib/languages/cpp';
import hlCsharp from 'highlight.js/lib/languages/csharp';
import hlCss from 'highlight.js/lib/languages/css';
import hlDiff from 'highlight.js/lib/languages/diff';
import hlDockerfile from 'highlight.js/lib/languages/dockerfile';
import hlGo from 'highlight.js/lib/languages/go';
import hlGraphql from 'highlight.js/lib/languages/graphql';
import hlIni from 'highlight.js/lib/languages/ini';
import hlJava from 'highlight.js/lib/languages/java';
import hlJavascript from 'highlight.js/lib/languages/javascript';
import hlJson from 'highlight.js/lib/languages/json';
import hlKotlin from 'highlight.js/lib/languages/kotlin';
import hlMarkdown from 'highlight.js/lib/languages/markdown';
import hlPhp from 'highlight.js/lib/languages/php';
import hlPlaintext from 'highlight.js/lib/languages/plaintext';
import hlPython from 'highlight.js/lib/languages/python';
import hlRuby from 'highlight.js/lib/languages/ruby';
import hlRust from 'highlight.js/lib/languages/rust';
import hlShell from 'highlight.js/lib/languages/shell';
import hlSql from 'highlight.js/lib/languages/sql';
import hlSwift from 'highlight.js/lib/languages/swift';
import hlTypescript from 'highlight.js/lib/languages/typescript';
import hlXml from 'highlight.js/lib/languages/xml';
import hlYaml from 'highlight.js/lib/languages/yaml';

hljs.registerLanguage('bash', hlBash);
hljs.registerLanguage('c', hlC);
hljs.registerLanguage('cpp', hlCpp);
hljs.registerLanguage('csharp', hlCsharp);
hljs.registerLanguage('css', hlCss);
hljs.registerLanguage('diff', hlDiff);
hljs.registerLanguage('dockerfile', hlDockerfile);
hljs.registerLanguage('go', hlGo);
hljs.registerLanguage('graphql', hlGraphql);
hljs.registerLanguage('ini', hlIni);
hljs.registerLanguage('java', hlJava);
hljs.registerLanguage('javascript', hlJavascript);
hljs.registerLanguage('json', hlJson);
hljs.registerLanguage('kotlin', hlKotlin);
hljs.registerLanguage('markdown', hlMarkdown);
hljs.registerLanguage('php', hlPhp);
hljs.registerLanguage('plaintext', hlPlaintext);
hljs.registerLanguage('python', hlPython);
hljs.registerLanguage('ruby', hlRuby);
hljs.registerLanguage('rust', hlRust);
hljs.registerLanguage('shell', hlShell);
hljs.registerLanguage('sql', hlSql);
hljs.registerLanguage('swift', hlSwift);
hljs.registerLanguage('typescript', hlTypescript);
hljs.registerLanguage('xml', hlXml);
hljs.registerLanguage('yaml', hlYaml);
import { BASE } from '$lib/api';
import { getToken } from '$lib/stores/session';

// Configure a dedicated Marked instance with GFM and syntax highlighting via
// highlight.js. A fresh instance (instead of `marked.use()` on the global
// singleton) keeps this renderer from leaking into other marked callers and
// vice versa (#1317).
const renderer = new Renderer();
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
const mdParser = new Marked({ gfm: true, breaks: true });
mdParser.use({ renderer });

// Configure DOMPurify for safe markdown rendering — only when a DOM exists.
// Without `window` (SSR), dompurify@3 is a stub whose `sanitize` returns input
// untouched, so its configuration is meaningless there and renderMarkdown must
// never emit markup (#1317).
// NOTE: `rel` is intentionally NOT in ALLOWED_ATTR — a rendered note could
// otherwise carry `target="_blank" rel="opener"` (reverse tabnabbing). Instead
// the hook below forces a safe `rel` on every anchor that sets `target`.
if (typeof window !== 'undefined') {
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
}

/** Escape `& < > " '` so untrusted text can be interpolated into HTML. */
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Extract Obsidian wikilinks (`[[title]]` or `[[title|alias]]`) into escaped
 * HTML spans, leaving inert placeholders behind for the marked/DOMPurify
 * pipeline (#1317).
 *
 * Title/alias are note-author-controlled. Building the span *after*
 * sanitization (see `injectWikilinks`) guarantees the fields stay escaped
 * literals: before, they were interpolated into markup upstream of marked,
 * so `[[x|<img …>]]` injected allowlisted tags that survived DOMPurify.
 */
const WIKILINK_TOKEN = '@@JOIDY_WIKILINK_';

function extractWikilinks(md: string): { md: string; spans: string[] } {
  const spans: string[] = [];
  const out = md.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (_match, title, alias) => {
    const display = escapeHtml(alias || title);
    spans.push(`<span class="wikilink" data-title="${escapeHtml(title.trim())}">${display}</span>`);
    return `${WIKILINK_TOKEN}${spans.length - 1}@@`;
  });
  return { md: out, spans };
}

/** Swap wikilink placeholders for their escaped spans after sanitization. */
function injectWikilinks(html: string, spans: string[]): string {
  let out = html;
  for (let i = 0; i < spans.length; i++) {
    out = out.replace(`${WIKILINK_TOKEN}${i}@@`, spans[i]);
  }
  return out;
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

  const { md: tokenized, spans } = extractWikilinks(preprocessed);

  const html = String(mdParser.parse(tokenized));
  // Without a DOM, dompurify@3 returns the input unsanitized — never emit that
  // markup. Rendering is client-side only, so an empty string is the safe
  // SSR fallback (#1317).
  if (typeof window === 'undefined') return '';
  return authorizeUploadUrls(injectWikilinks(DOMPurify.sanitize(html), spans));
}
