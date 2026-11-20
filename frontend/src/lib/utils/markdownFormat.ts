// Markdown formatting helpers extracted from NoteEditor.svelte (#210).

export interface FormatSpec {
  prefix: string;
  suffix: string;
  block?: string;
  multiline?: boolean;
}

export const FORMATTERS: Record<string, FormatSpec> = {
  bold: { prefix: '**', suffix: '**' },
  italic: { prefix: '_', suffix: '_' },
  strikethrough: { prefix: '~~', suffix: '~~' },
  h1: { prefix: '# ', suffix: '', block: '# ' },
  h2: { prefix: '## ', suffix: '', block: '## ' },
  h3: { prefix: '### ', suffix: '', block: '### ' },
  ul: { prefix: '- ', suffix: '', block: '- ', multiline: true },
  ol: { prefix: '1. ', suffix: '', block: '1. ', multiline: true },
  link: { prefix: '[', suffix: '](url)' },
  quote: { prefix: '> ', suffix: '', block: '> ', multiline: true },
  code: { prefix: '```\n', suffix: '\n```', block: '```\n' },
};

/**
 * Link URL scheme allowlist (#1331). Accepts http(s), mailto, and relative
 * URLs (`page.md`, `./a`, `/abs`, `#anchor`); rejects everything else —
 * `javascript:`, `data:`, `vbscript:`, `file:`, `ftp:`, etc.
 *
 * Uses the WHATWG URL parser against a dummy https base so obfuscation like
 * `java\tscript:` is normalized before the scheme is checked, and relative
 * references resolve to the base's https scheme.
 */
export function isAllowedLinkUrl(url: string): boolean {
  const trimmed = url.trim();
  if (!trimmed) return false;
  try {
    const parsed = new URL(trimmed, 'https://joidy.invalid/');
    return (
      parsed.protocol === 'http:' || parsed.protocol === 'https:' || parsed.protocol === 'mailto:'
    );
  } catch {
    return false;
  }
}

// Applies a format action to a WysiwygEditor instance. `wysiwygRef` is the
// component instance (typed loosely — exposes toggle* helpers). `linkUrl` is
// the URL collected by the caller's dialog (window.prompt() was removed for
// a11y, #1308); the 'link' action is a no-op without it.
export function applyWysiwygFormat(wysiwygRef: any, type: string, linkUrl?: string) {
  switch (type) {
    case 'bold':
      wysiwygRef.toggleBold();
      break;
    case 'italic':
      wysiwygRef.toggleItalic();
      break;
    case 'strikethrough':
      wysiwygRef.toggleStrike();
      break;
    case 'h1':
      wysiwygRef.toggleH1();
      break;
    case 'h2':
      wysiwygRef.toggleH2();
      break;
    case 'h3':
      wysiwygRef.toggleH3();
      break;
    case 'ul':
      wysiwygRef.toggleBulletList();
      break;
    case 'ol':
      wysiwygRef.toggleOrderedList();
      break;
    case 'link':
      // Scheme allowlist (#1331): reject javascript:/data:/etc. URLs before
      // they reach the editor DOM. WysiwygEditor.setLink re-validates too.
      if (linkUrl && isAllowedLinkUrl(linkUrl)) wysiwygRef.setLink(linkUrl);
      break;
    case 'quote':
      wysiwygRef.toggleBlockquote();
      break;
    case 'code':
      wysiwygRef.toggleCodeBlock();
      break;
  }
}

// Computes the new content and caret position for a raw-textarea markdown
// format action. Returns null when the format type is unknown.
export function computeFormatEdit(
  content: string,
  selectionStart: number,
  selectionEnd: number,
  type: string
): { content: string; caret: number } | null {
  const fmt = FORMATTERS[type];
  if (!fmt) return null;
  const selected = content.substring(selectionStart, selectionEnd);

  let insertion: string;

  if (fmt.multiline && selected) {
    const lines = selected
      .split('\n')
      .map((l) => fmt.block + l)
      .join('\n');
    insertion = lines;
  } else if (fmt.block && !selected) {
    insertion = fmt.block;
  } else if (selected) {
    insertion = fmt.prefix + selected + fmt.suffix;
  } else {
    insertion = fmt.prefix + fmt.suffix;
  }

  const before = content.substring(0, selectionStart);
  const after = content.substring(selectionEnd);
  const newContent = before + insertion + after;

  const pos =
    selectionStart +
    (fmt.block && !selected
      ? fmt.block.length
      : insertion.length - (fmt.suffix ? insertion.length - fmt.prefix.length : 0));

  const caret = !selected && fmt.suffix ? selectionStart + fmt.prefix.length : pos;

  return { content: newContent, caret };
}

// Inserts raw text at the caret position of a textarea selection.
export function insertTextAt(
  content: string,
  selectionStart: number,
  selectionEnd: number,
  text: string
): { content: string; caret: number } {
  const before = content.substring(0, selectionStart);
  const after = content.substring(selectionEnd);
  return {
    content: before + text + after,
    caret: selectionStart + text.length,
  };
}
