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

// Applies a format action to a WysiwygEditor instance. `wysiwygRef` is the
// component instance (typed loosely — exposes toggle* helpers).
export function applyWysiwygFormat(wysiwygRef: any, type: string) {
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
      const url = prompt('URL del enlace:');
      if (url) wysiwygRef.setLink(url);
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
