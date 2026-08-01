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

// Configure DOMPurify for safe markdown rendering
DOMPurify.setConfig({
  ALLOWED_TAGS: [
    'p', 'br', 'strong', 'em', 'a', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'pre', 'code', 'blockquote',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'span', 'div', 'hr', 'img', 'del', 'ins', 'sup', 'sub',
  ],
  ALLOWED_ATTR: ['href', 'target', 'rel', 'src', 'alt', 'class', 'data-title'],
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
 * Render markdown to sanitized HTML.
 *
 * @param md        - Raw markdown string
 * @param options   - Optional flags
 * @param options.hideTagsLine - Remove `# Tags: ...` lines before rendering
 * @param options.hasTags      - Whether tags exist (only strips tags line if true)
 */
export function renderMarkdown(
  md: string,
  options: { hideTagsLine?: boolean; hasTags?: boolean } = {},
): string {
  if (!md.trim()) {
    return '<p style="color:var(--text-muted);font-style:italic;">Escribe algo para ver el preview...</p>';
  }

  let preprocessed = md;
  if (options.hideTagsLine && options.hasTags) {
    preprocessed = preprocessed.replace(/^#\s*Tags?:\s*.*$/gim, '');
  }

  preprocessed = preprocessWikilinks(preprocessed);

  return DOMPurify.sanitize(String(marked.parse(preprocessed)));
}
