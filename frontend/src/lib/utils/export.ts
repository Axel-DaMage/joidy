import type { Note } from '$lib/api';
import { copyToClipboard } from './clipboard';

export function exportToMarkdown(note: Note): string {
  let md = `# ${note.title}\n\n`;

  if (note.tags.length > 0) {
    md += `**Tags:** ${note.tags.map(t => `[[${t}]]`).join(', ')}\n\n`;
  }

  md += note.content;

  if (note.source_path) {
    md += `\n\n---\n*Fuente: ${note.source_path}*`;
  }

  return md;
}

export function downloadMarkdown(note: Note) {
  const md = exportToMarkdown(note);
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${note.title.replace(/[^a-z0-9]/gi, '_')}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function copyNoteAsMarkdown(note: Note): Promise<boolean> {
  const md = exportToMarkdown(note);
  return copyToClipboard(md);
}

export function exportToHTML(note: Note): string {
  const html = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>${note.title}</title>
  <style>
    body { font-family: -apple-system, system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }
    h1 { border-bottom: 1px solid #eee; padding-bottom: 10px; }
    .meta { color: #666; font-size: 14px; margin-bottom: 20px; }
    pre { background: #f5f5f5; padding: 16px; overflow-x: auto; }
    code { background: #f5f5f5; padding: 2px 6px; }
  </style>
</head>
<body>
  <h1>${note.title}</h1>
  <div class="meta">
    ${note.tags.length > 0 ? `Tags: ${note.tags.join(', ')}` : ''}
    ${note.source_path ? `<br>Fuente: ${note.source_path}` : ''}
  </div>
  <div class="content">${note.content}</div>
</body>
</html>
  `.trim();
  return html;
}

export function downloadHTML(note: Note) {
  const html = exportToHTML(note);
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${note.title.replace(/[^a-z0-9]/gi, '_')}.html`;
  a.click();
  URL.revokeObjectURL(url);
}

export function exportToJSON(notes: Note[]) {
  const json = JSON.stringify(notes, null, 2);
  const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `joidy-export-${new Date().toISOString().split('T')[0]}.json`;
  a.click();
  URL.revokeObjectURL(url);
}