// Tree-shakeable access to the lucide-svelte icon set.
//
// Uses a namespace import from 'lucide-svelte' which bundles all icon
// components into a single chunk. This is the most reliable approach across
// Vite dev server, production build, and Docker — previous attempts with
// import.meta.glob (both eager and lazy) caused module resolution failures
// in dev or production (#684, #693).
//
// Bundle size trade-off (#209): the full icon set is ~1900 icons but the
// namespace import lets Vite/Rollup tree-shake unused icons if only some
// are referenced. In practice, DynamicIcon/StreakIcon resolve icons by name
// at runtime so the full set is needed.

import * as LucideIcons from 'lucide-svelte';

// kebab-case file name → PascalCase (e.g. "a-arrow-down" → "AArrowDown",
// "file-audio-2" → "FileAudio2"). Matches the PascalCase keys that the
// lucide-svelte namespace export uses.
function kebabToPascal(kebab: string): string {
  return kebab
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('');
}

// Build a map of PascalCase name → icon component (synchronous).
const _icons = new Map<string, any>();
for (const [name, comp] of Object.entries(LucideIcons)) {
  if (typeof comp === 'function' || typeof comp === 'object') {
    _icons.set(name, comp);
  }
}

// ── Legacy alias map ────────────────────────────────────────────────────────
// lucide-svelte v1.0.0 renamed many icons (#783). Data-driven icon names
// (streaks, achievements, DynamicIcon name="…") may still reference the old
// PascalCase names — especially anything persisted in the DB. Map them to
// their current equivalents so existing data keeps rendering without a
// migration.
const LEGACY_ALIASES: Record<string, string> = {
  AlertTriangle: 'TriangleAlert',
  BarChart: 'ChartColumn',
  BarChart3: 'ChartNoAxesColumn',
  CheckCircle: 'CircleCheckBig',
  CheckSquare: 'SquareCheckBig',
  Edit: 'SquarePen',
  FileEdit: 'FilePen',
  Filter: 'ListFilter',
  Layout: 'LayoutDashboard',
  Loader2: 'LoaderCircle',
  PieChart: 'ChartPie',
  DownloadCloud: 'CloudDownload',
};

/**
 * All available lucide icon names in PascalCase (e.g. "Search", "FileText").
 * Used by the icon picker to render its grid.
 */
export const ALL_LUCIDE_ICON_NAMES: string[] = Array.from(_icons.keys()).sort();

/**
 * Resolve a lucide icon component by name, synchronously.
 *
 * Accepts either PascalCase ("FileText") or kebab-case ("file-text"). Returns
 * the icon's Svelte component, or `null` when the name is unknown so callers
 * can fall back to a placeholder (e.g. `Circle`).
 */
export function getLucideIcon(name: string): any | null {
  if (!name) return null;
  const alias = LEGACY_ALIASES[name] ?? LEGACY_ALIASES[kebabToPascal(name)];
  const resolved = alias ?? name;
  return _icons.get(resolved) ?? _icons.get(kebabToPascal(resolved)) ?? null;
}

/**
 * Lazily import a lucide icon component by name.
 *
 * Kept for backward compatibility — now resolves synchronously since all
 * icons are bundled. Prefer `getLucideIcon` for new code.
 */
export async function loadLucideIcon(name: string): Promise<any | null> {
  return getLucideIcon(name);
}

/**
 * Synchronous check whether an icon name exists in the lucide set.
 */
export function hasLucideIcon(name: string): boolean {
  if (!name) return false;
  const alias = LEGACY_ALIASES[name] ?? LEGACY_ALIASES[kebabToPascal(name)];
  const resolved = alias ?? name;
  return _icons.has(resolved) || _icons.has(kebabToPascal(resolved));
}
