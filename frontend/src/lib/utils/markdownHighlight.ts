// Editor syntax highlighter extracted from NoteEditor.svelte (#210).
// Produces a lightweight HTML overlay for the raw-markdown textarea backdrop.

export function highlightMarkdown(text: string): string {
  if (!text) return '';
  let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  // Multiline code blocks
  html = html.replace(/^(`{3,})(.*)$/gm, '<span style="color: var(--text-muted);">$1$2</span>');

  // Headers
  html = html.replace(/^(#{1,6})(\s+.+)$/gm, (match, hashes, rest) => {
    const level = hashes.length;
    return `<span style="color: var(--md-h${level}); font-weight: 500;">${hashes}${rest}</span>`;
  });

  // Blockquotes
  html = html.replace(
    /^(&gt;\s*)(.*)$/gm,
    '<span style="color: var(--text-secondary); border-left: 2px solid var(--border); padding-left: 6px; font-style: italic;">$1$2</span>'
  );

  // Lists (unordered and ordered)
  html = html.replace(
    /^(\s*)([-*+]|\d+\.)(\s+)/gm,
    '$1<span style="color: var(--md-h1, var(--xp)); font-weight: bold;">$2</span>$3'
  );

  // Bold + Italic
  html = html.replace(
    /(\*\*\*|___)([^\s](?:.*?[^\s])?)\1/g,
    '<span style="font-weight: bold; font-style: italic; color: var(--md-h2, var(--xp));">$1$2$1</span>'
  );

  // Bold
  html = html.replace(
    /(\*\*|__)([^\s](?:.*?[^\s])?)\1/g,
    '<span style="font-weight: bold; color: var(--text-primary);">$1$2$1</span>'
  );

  // Italic (using negative lookbehinds/lookaheads to prevent matching bold borders)
  html = html.replace(
    /(?<!\*)\*([^\s\*](?:.*?[^\s\*])?)\*(?!\*)/g,
    '<span style="font-style: italic; color: var(--text-secondary);">*$1*</span>'
  );
  html = html.replace(
    /(?<!_)_([^\s_](?:.*?[^\s_])?)_(?!_)/g,
    '<span style="font-style: italic; color: var(--text-secondary);">_$1_</span>'
  );

  // Strikethrough
  html = html.replace(
    /(~~)([^\s](?:.*?[^\s])?)\1/g,
    '<span style="text-decoration: line-through; opacity: 0.6;">$1$2$1</span>'
  );

  // Inline code
  html = html.replace(
    /(`)(.*?)\1/g,
    '<span style="background: var(--elevated); color: var(--md-h1, var(--xp)); border-radius: 3px; padding: 0 2px;">$1$2$1</span>'
  );

  // Links (standard markdown)
  html = html.replace(
    /(\[)([^\]]+)(\])(\()([^\)]+)(\))/g,
    '<span style="color: var(--text-muted)">$1</span><span style="color: var(--md-h2, var(--xp))">$2</span><span style="color: var(--text-muted)">$3$4</span><span style="color: var(--text-muted); text-decoration: underline;">$5</span><span style="color: var(--text-muted)">$6</span>'
  );

  // Tags line
  html = html.replace(
    /^(#\s*Tags?:\s*)(.*)$/gim,
    '<span style="opacity: 0.3; font-size: 0.9em;">$1$2</span>'
  );

  // Obsidian Wikilinks & Tags
  html = html.replace(
    /(#Tag:\s*)?(\[\[)([^\]]+)(\]\])/g,
    (match, tagPrefix, openBracket, content, closeBracket) => {
      if (tagPrefix) {
        return `<span style="opacity: 0.3; font-size: 0.9em;">${tagPrefix}${openBracket}${content}${closeBracket}</span>`;
      }
      return `<span style="color: var(--text-muted)">${openBracket}</span><span style="color: var(--md-h2, var(--xp))">${content}</span><span style="color: var(--text-muted)">${closeBracket}</span>`;
    }
  );

  // Ensure trailing newlines render correctly
  if (html.endsWith('\n')) {
    html += '<br/>';
  }

  return html;
}
