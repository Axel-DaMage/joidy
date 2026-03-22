import type { Note } from '$lib/api';

export interface TreeNode {
  type: 'folder' | 'file';
  name: string;
  path: string;       // unique key for collapse state
  icon: string;
  note?: Note;
  children: TreeNode[];
}

// ── Icon assignment ────────────────────────────────────────────────────────────

function normalize(s: string): string {
  return s.replace(/^\d+\s*[-–]\s*/, '').toLowerCase().trim();
}

const FOLDER_ICONS: [RegExp, string][] = [
  [/joidy/,                          '🌱'],
  [/daily|diario|journal/,           '📅'],
  [/notas?\s*crud|raw|borrador/,     '📝'],
  [/tag|etiquet|categor/,            '🏷️'],
  [/recurso|resource|referencia/,    '📦'],
  [/notas?\s*complet|complete/,      '✅'],
  [/plantilla|template/,             '📋'],
  [/repo|repositorio|git/,           '🗂️'],
  [/rutina|routine|habit/,           '🔄'],
  [/kotlin/,                         '⚡'],
  [/java(?!script)/,                 '☕'],
  [/python/,                         '🐍'],
  [/javascript|typescript|js|ts/,    '🟨'],
  [/devops|docker|k8s|kubernetes/,   '⚙️'],
  [/linux|kernel|unix/,              '🐧'],
  [/matem|math/,                     '➗'],
  [/fullstack|front.?end|back.?end|web/, '💻'],
  [/dba|database|sql|db/,            '🗃️'],
  [/seguridad|security|ciber/,       '🔒'],
  [/litera|libro|book/,              '📚'],
  [/filosof|etica|ethic/,            '⚖️'],
  [/evento|event|meetup|conference/, '📍'],
  [/proyecto|project/,               '🚀'],
  [/idea/,                           '💡'],
  [/vim|nvim|neovim/,                '🖊️'],
  [/certif|curso|course/,            '🎓'],
  [/evaluac|review/,                 '📊'],
  [/oss|open.?source/,               '🌐'],
];

export function getFolderIcon(name: string): string {
  const n = normalize(name);
  for (const [re, icon] of FOLDER_ICONS) {
    if (re.test(n)) return icon;
  }
  return '📁';
}

const FILE_ICONS: [RegExp, string][] = [
  [/kotlin|\.kt/,                    '⚡'],
  [/java(?!script)/,                 '☕'],
  [/python|\.py/,                    '🐍'],
  [/javascript|typescript|react|vue|svelte/, '🟨'],
  [/docker|container|imagen/,        '🐳'],
  [/kubernetes|k8s|helm/,            '⚙️'],
  [/linux|kernel|bash|shell|zsh/,    '🐧'],
  [/git|github|commit|branch/,       '🔀'],
  [/sql|database|postgres|mysql|mongo/, '🗃️'],
  [/security|seguridad|hack|vuln|cve/, '🔒'],
  [/matem|ecuac|formula|calcul/,     '➗'],
  [/devops|ci.?cd|pipeline/,         '⚙️'],
  [/libro|book|lectura|reading/,     '📖'],
  [/reunion|meeting|reu\b/,          '👥'],
  [/objetivo|goal|target/,           '🎯'],
  [/daily|rutina|habit|routine/,     '📅'],
  [/idea|concepto|brainstorm/,       '💡'],
  [/evento|event|conference|meetup/, '📍'],
  [/vim|nvim|neovim/,                '🖊️'],
  [/certif|examen|exam|curso/,       '🎓'],
  [/project|proyecto/,               '🚀'],
  [/oss|open.?source/,               '🌐'],
  [/filosofi|etica|budis|nietzsche|stoic/, '⚖️'],
  [/cloud|aws|gcp|azure/,            '☁️'],
  [/api|rest|graphql|endpoint/,      '🔌'],
  [/test|testing|bdd|tdd/,           '🧪'],
  [/design|pattern|arquitectura/,    '🏗️'],
];

export function getFileIcon(title: string, content: string): string {
  const text = (title + ' ' + content.slice(0, 200)).toLowerCase();
  for (const [re, icon] of FILE_ICONS) {
    if (re.test(text)) return icon;
  }
  // Detect code-heavy notes
  if ((content.match(/```/g) ?? []).length >= 2) return '📄';
  return '📝';
}

// ── Tree builder ───────────────────────────────────────────────────────────────

interface RawNode {
  type: 'folder' | 'file';
  name: string;
  note?: Note;
  children: Record<string, RawNode>;
}

export function buildTree(notes: Note[], search = ''): TreeNode[] {
  const root: Record<string, RawNode> = {};

  const filtered = search
    ? notes.filter(n =>
        n.title.toLowerCase().includes(search.toLowerCase()) ||
        n.tags.some(t => t.includes(search.toLowerCase()))
      )
    : notes;

  for (const note of filtered) {
    if (note.source_path) {
      // Strip /vault/ or /vault prefix
      const rel = note.source_path.replace(/^\/vault\/?/, '');
      const parts = rel.split('/').filter(Boolean);

      let node = root;
      for (let i = 0; i < parts.length - 1; i++) {
        const seg = parts[i];
        if (!node[seg]) {
          node[seg] = { type: 'folder', name: seg, children: {} };
        }
        node = node[seg].children;
      }
      const filename = parts[parts.length - 1] ?? note.title;
      const stem = filename.replace(/\.md$/, '');
      node[stem] = { type: 'file', name: stem, note, children: {} };
    } else {
      // Joidy-created notes → virtual folder
      const key = '✦ joidy';
      if (!root[key]) root[key] = { type: 'folder', name: '✦ joidy', children: {} };
      root[key].children[note.title] = { type: 'file', name: note.title, note, children: {} };
    }
  }

  return rawToTreeNodes(root, '');
}

function rawToTreeNodes(map: Record<string, RawNode>, parentPath: string): TreeNode[] {
  return Object.entries(map)
    .map(([key, raw]) => {
      const path = parentPath ? `${parentPath}/${key}` : key;
      if (raw.type === 'folder') {
        const children = rawToTreeNodes(raw.children, path);
        return {
          type: 'folder' as const,
          name: raw.name,
          path,
          icon: getFolderIcon(raw.name),
          children,
        };
      } else {
        return {
          type: 'file' as const,
          name: raw.name,
          path,
          icon: getFileIcon(raw.note?.title ?? '', raw.note?.content ?? ''),
          note: raw.note,
          children: [],
        };
      }
    })
    .sort((a, b) => {
      // Folders first, then files; _joidy last
      if (a.name.startsWith('_') && !b.name.startsWith('_')) return 1;
      if (!a.name.startsWith('_') && b.name.startsWith('_')) return -1;
      if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
      return a.name.localeCompare(b.name, 'es', { numeric: true });
    });
}
