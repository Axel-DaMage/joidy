import type { Note } from '$lib/api';

export interface TreeNode {
  type: 'folder' | 'file';
  name: string;
  path: string;       // unique key for collapse state
  icon: string;
  color?: string;
  pack?: string;
  note?: Note;
  children: TreeNode[];
}

// ── Icon assignment ────────────────────────────────────────────────────────────

function normalize(s: string): string {
  return s.replace(/^\d+\s*[-–]\s*/, '').toLowerCase().trim();
}

const FOLDER_ICONS: [RegExp, string][] = [
  [/joidy/,                          'Leaf'],
  [/daily|diario|journal/,           'Calendar'],
  [/notas?\s*crud|raw|borrador/,     'PenTool'],
  [/tag|etiquet|categor/,            'Tag'],
  [/recurso|resource|referencia/,    'Package'],
  [/notas?\s*complet|complete/,      'Check'],
  [/plantilla|template/,             'ClipboardList'],
  [/repo|repositorio|git/,           'GitBranch'],
  [/rutina|routine|habit/,           'RefreshCw'],
  [/kotlin/,                         'Zap'],
  [/java(?!script)/,                 'Coffee'],
  [/python/,                         'Code'],
  [/javascript|typescript|js|ts/,    'Terminal'],
  [/devops|docker|k8s|kubernetes/,   'Settings'],
  [/linux|kernel|unix/,              'Terminal'],
  [/matem|math/,                     'Calculator'],
  [/fullstack|front.?end|back.?end|web/, 'Monitor'],
  [/dba|database|sql|db/,            'Database'],
  [/seguridad|security|ciber/,       'Lock'],
  [/litera|libro|book/,              'BookOpen'],
  [/filosof|etica|ethic/,            'Scale'],
  [/evento|event|meetup|conference/, 'MapPin'],
  [/proyecto|project/,               'Rocket'],
  [/idea/,                           'Lightbulb'],
  [/vim|nvim|neovim/,                'Pen'],
  [/certif|curso|course/,            'GraduationCap'],
  [/evaluac|review/,                 'BarChart'],
  [/oss|open.?source/,               'Globe'],
];

export function getFolderIcon(name: string): string {
  const n = normalize(name);
  for (const [re, icon] of FOLDER_ICONS) {
    if (re.test(n)) return icon;
  }
  return 'Folder';
}

const FILE_ICONS: [RegExp, string][] = [
  [/kotlin|\.kt/,                    'Zap'],
  [/java(?!script)/,                 'Coffee'],
  [/python|\.py/,                    'Code'],
  [/javascript|typescript|react|vue|svelte/, 'Terminal'],
  [/docker|container|imagen/,        'Package'],
  [/kubernetes|k8s|helm/,            'Settings'],
  [/linux|kernel|bash|shell|zsh/,    'Terminal'],
  [/git|github|commit|branch/,       'GitBranch'],
  [/sql|database|postgres|mysql|mongo/, 'Database'],
  [/security|seguridad|hack|vuln|cve/, 'Lock'],
  [/matem|ecuac|formula|calcul/,     'Calculator'],
  [/devops|ci.?cd|pipeline/,         'Settings'],
  [/libro|book|lectura|reading/,     'BookOpen'],
  [/reunion|meeting|reu\b/,          'Users'],
  [/objetivo|goal|target/,           'Target'],
  [/daily|rutina|habit|routine/,     'Calendar'],
  [/idea|concepto|brainstorm/,       'Lightbulb'],
  [/evento|event|conference|meetup/, 'MapPin'],
  [/vim|nvim|neovim/,                'Pen'],
  [/certif|examen|exam|curso/,       'GraduationCap'],
  [/project|proyecto/,               'Rocket'],
  [/oss|open.?source/,               'Globe'],
  [/filosofi|etica|budis|nietzsche|stoic/, 'Scale'],
  [/cloud|aws|gcp|azure/,            'Cloud'],
  [/api|rest|graphql|endpoint/,      'Plug'],
  [/test|testing|bdd|tdd/,           'Code'],
  [/design|pattern|arquitectura/,    'Package'],
];

export function extractFrontmatter(content: string) {
  const m = content.match(/^---\n([\s\S]*?)\n---/);
  if (!m) return { icon: null, color: null, pack: null };
  const yaml = m[1];
  const ic = yaml.match(/(?:^|\n)icon:\s*([^\n]+)/);
  const cl = yaml.match(/(?:^|\n)iconColor:\s*([^\n]+)/);
  const pk = yaml.match(/(?:^|\n)iconPack:\s*([^\n]+)/);
  return {
    icon: ic ? ic[1].trim() : null,
    color: cl ? cl[1].trim() : null,
    pack: pk ? pk[1].trim() : null
  };
}

export function getFileIcon(title: string, content: string): string {
  const fm = extractFrontmatter(content);
  if (fm.icon) return fm.icon;

  const text = (title + ' ' + content.slice(0, 200)).toLowerCase();
  for (const [re, icon] of FILE_ICONS) {
    if (re.test(text)) return icon;
  }
  if ((content.match(/```/g) ?? []).length >= 2) return 'FileCode';
  return 'File';
}

// ── Flat node (pre-processed, avoids recursive component rendering) ───────────

export interface FlatNode {
  type: 'folder' | 'file';
  name: string;
  path: string;
  icon: string;
  color?: string;
  pack?: string;
  depth: number;
  note?: Note;
  childCount: number;
}

export function flattenTree(nodes: TreeNode[], collapsed: Set<string>, depth = 0): FlatNode[] {
  const result: FlatNode[] = [];
  for (const node of nodes) {
    if (node.type === 'folder') {
      result.push({ type: 'folder', name: node.name, path: node.path, icon: node.icon, color: node.color, pack: node.pack, depth, childCount: node.children.length });
      if (!collapsed.has(node.path)) {
        result.push(...flattenTree(node.children, collapsed, depth + 1));
      }
    } else {
      result.push({ type: 'file', name: node.name, path: node.path, icon: node.icon, color: node.color, pack: node.pack, depth, note: node.note, childCount: 0 });
    }
  }
  return result;
}

// ── Tree builder ───────────────────────────────────────────────────────────────

interface RawNode {
  type: 'folder' | 'file';
  name: string;
  note?: Note;
  children: Record<string, RawNode>;
}

export type SortMode = 'az' | 'za' | 'edit-new' | 'edit-old' | 'create-new' | 'create-old';

export function buildTree(notes: Note[], search = '', showTrash = false, showHidden = false, sortMode: SortMode = 'az'): TreeNode[] {
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

      if (!showTrash && parts.some(p => p === '.trash')) continue;
      if (!showHidden && parts.some(p => p !== '.trash' && p.startsWith('.'))) continue;

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

  return rawToTreeNodes(root, '', sortMode);
}

function rawToTreeNodes(map: Record<string, RawNode>, parentPath: string, sortMode: SortMode): TreeNode[] {
  return Object.entries(map)
    .map(([key, raw]) => {
      const path = parentPath ? `${parentPath}/${key}` : key;
      if (raw.type === 'folder') {
        const children = rawToTreeNodes(raw.children, path, sortMode);
        return {
          type: 'folder' as const,
          name: raw.name,
          path,
          icon: getFolderIcon(raw.name),
          children,
        };
      } else {
        const fm = raw.note ? extractFrontmatter(raw.note.content) : { icon: null, color: null, pack: null };
        return {
          type: 'file' as const,
          name: raw.name,
          path,
          icon: fm.icon || getFileIcon(raw.note?.title ?? '', raw.note?.content ?? ''),
          color: fm.color || undefined,
          pack: fm.pack || undefined,
          note: raw.note,
          children: [],
        };
      }
    })
    .sort((a, b) => {
      // Always put folders first, _joidy last
      if (a.name.startsWith('_') && !b.name.startsWith('_')) return 1;
      if (!a.name.startsWith('_') && b.name.startsWith('_')) return -1;
      if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;

      // Both are of same type. If folders, always A-Z (or Z-A)
      if (a.type === 'folder') {
        const cmp = a.name.localeCompare(b.name, 'es', { numeric: true });
        return sortMode === 'za' ? -cmp : cmp;
      }

      // Both are files
      if (sortMode === 'az') return a.name.localeCompare(b.name, 'es', { numeric: true });
      if (sortMode === 'za') return b.name.localeCompare(a.name, 'es', { numeric: true });

      const d1 = new Date(a.note?.updated_at || 0).getTime();
      const d2 = new Date(b.note?.updated_at || 0).getTime();
      const c1 = new Date(a.note?.created_at || 0).getTime();
      const c2 = new Date(b.note?.created_at || 0).getTime();

      if (sortMode === 'edit-new') return d2 - d1;
      if (sortMode === 'edit-old') return d1 - d2;
      if (sortMode === 'create-new') return c2 - c1;
      if (sortMode === 'create-old') return c1 - c2;
      return 0;
    });
}
