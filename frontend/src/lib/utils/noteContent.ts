// Pure helpers extracted from NoteEditor.svelte (#210).

export function extractTagsFromContent(text: string): string[] {
  const extracted = new Set<string>();

  // Match line like: # Tags: [[tag1]] [[tag2]]
  const lineRegex = /^#\s*Tags?:\s*(.*)$/gim;
  let lineMatch;
  while ((lineMatch = lineRegex.exec(text)) !== null) {
    const lineTags = lineMatch[1];
    const tagRegex = /\[\[([^\]|]+)(?:\|[^\]]+)?\]\]/g;
    let tagMatch;
    while ((tagMatch = tagRegex.exec(lineTags)) !== null) {
      extracted.add(tagMatch[1].trim().toLowerCase());
    }
  }

  // Match individual #Tag: [[tag]]
  const regex = /#Tag:\s*\[\[([^\]|]+)(?:\|[^\]]+)?\]\]/gi;
  let match;
  while ((match = regex.exec(text)) !== null) {
    extracted.add(match[1].trim().toLowerCase());
  }

  return Array.from(extracted);
}

export function escapeRegExp(string: string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Returns the updated content with `key: value` written into (or added to) the
// YAML frontmatter block. Callers persist the result back into editor state.
export function updateFrontmatterInContent(content: string, key: string, value: string): string {
  const m = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (m) {
    let yaml = m[1];
    const regex = new RegExp(`(?:^|\\n)${key}:.*`);
    if (regex.test(yaml)) {
      yaml = yaml.replace(regex, `\n${key}: ${value}`);
    } else {
      yaml += `\n${key}: ${value}`;
    }
    yaml = yaml.replace(/\n{2,}/g, '\n').trim();
    return content.replace(/^---\r?\n[\s\S]*?\r?\n---/, `---\n${yaml}\n---`);
  }
  return `---\n${key}: ${value}\n---\n\n` + content;
}
