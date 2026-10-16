import type { GraphNode } from '$lib/api';

// GraphNode extended with force-graph runtime properties is defined locally in
// KnowledgeGraphForce.svelte; these helpers only need the base GraphNode shape.

export interface ColorGroup {
  query: string;
  color: string;
}

// Pre-configured preset colors for Obsidian-style feel
export const COLOR_PRESETS = [
  '#f59e0b', // Amber
  '#10b981', // Emerald
  '#3b82f6', // Blue
  '#ec4899', // Pink
  '#8b5cf6', // Violet
  '#ef4444', // Red
  '#06b6d4', // Cyan
];

export const COLORS = {
  tag: '#1d9c73', // Emerald Green (Obsidian Tag default)
  note: '#8a8a8a', // Slate Grey (Obsidian Note default)
  unresolved: '#4f3e3e', // Dim crimson/dark grey (Obsidian Unresolved default)
  selected: '#e8a838', // Golden amber (Obsidian Selected default)
  default: '#666666',
} as const;

export const getNodeType = (n: GraphNode) => n.type;
export const getNodeLabel = (n: GraphNode) =>
  n.type === 'note' ? n.title || '' : n.name || n.title || '';

// Hex to RGBA helper for semi-transparent fills
export function hexToRgba(hex: string, alpha: number): string {
  const cleanHex = hex.replace('#', '');
  const r = parseInt(cleanHex.substring(0, 2), 16);
  const g = parseInt(cleanHex.substring(2, 4), 16);
  const b = parseInt(cleanHex.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// Lighten Hex color for radial gradient highlights
export function lightenColor(hex: string, percent: number): string {
  const cleanHex = hex.replace('#', '');
  let r = parseInt(cleanHex.substring(0, 2), 16);
  let g = parseInt(cleanHex.substring(2, 4), 16);
  let b = parseInt(cleanHex.substring(4, 6), 16);

  r = Math.min(255, Math.floor(r + (255 - r) * percent));
  g = Math.min(255, Math.floor(g + (255 - g) * percent));
  b = Math.min(255, Math.floor(b + (255 - b) * percent));

  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

// Obsidian Query parser for dynamic color groups
export function matchesQuery(node: GraphNode, queryStr: string): boolean {
  const q = queryStr.trim().toLowerCase();
  if (!q) return false;

  const label = getNodeLabel(node);
  const labelLower = label.toLowerCase();

  // 1. Tag query: tag:work or tag:#work
  if (q.startsWith('tag:')) {
    const targetTag = q.slice(4).replace(/^#/, '');
    if (node.type === 'tag') {
      return labelLower.replace(/^#/, '') === targetTag;
    }
    if (node.type === 'note' && node.tags) {
      return node.tags.some((t) => t.toLowerCase().replace(/^#/, '') === targetTag);
    }
    return false;
  }

  // 2. Path query: path:folder
  if (q.startsWith('path:')) {
    const targetPath = q.slice(5);
    if (node.type === 'note' && node.path) {
      return node.path.toLowerCase().includes(targetPath);
    }
    return false;
  }

  // 3. Title/file query: file:name or title:name
  if (q.startsWith('file:') || q.startsWith('title:')) {
    const targetTitle = q.slice(q.indexOf(':') + 1);
    return labelLower.includes(targetTitle);
  }

  // 4. Default general text search: matches title, tags
  const searchMatch = labelLower.includes(q);
  const tagMatch = node.tags ? node.tags.some((t) => t.toLowerCase().includes(q)) : false;
  return searchMatch || tagMatch;
}
