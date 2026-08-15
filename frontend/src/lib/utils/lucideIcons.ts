// Tree-shakeable access to the lucide-svelte icon set.
//
// Uses `import.meta.glob` with `eager: true` so that all icon components are
// available synchronously — no async placeholder flicker (#684). Vite places
// the glob result in a separate chunk, so the main bundle stays small (#209).
//
// The glob targets the compiled `.js` icon files shipped under
// `lucide-svelte/dist/icons/` via a bare module specifier, which Vite resolves
// through the module system — more robust than a relative `node_modules` path.

const iconModules = import.meta.glob('lucide-svelte/dist/icons/*.js', {
  eager: true,
  import: 'default',
});

// kebab-case file name → PascalCase (e.g. "a-arrow-down" → "AArrowDown",
// "file-audio-2" → "FileAudio2"). Matches the PascalCase keys that the old
// `import * as L` namespace used to expose.
function kebabToPascal(kebab: string): string {
  return kebab
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('');
}

// Build a map of PascalCase name → icon component (synchronous).
const _icons = new Map<string, any>();
for (const path of Object.keys(iconModules)) {
  // path looks like "lucide-svelte/dist/icons/a-arrow-down.js"
  const file = path.split('/').pop()!.replace(/\.js$/, '');
  _icons.set(kebabToPascal(file), (iconModules as Record<string, any>)[path]);
}

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
  return _icons.get(name) ?? _icons.get(kebabToPascal(name)) ?? null;
}

/**
 * Lazily import a lucide icon component by name.
 *
 * kept for backward compatibility — now resolves synchronously since all
 * icons are eagerly loaded. Prefer `getLucideIcon` for new code.
 */
export async function loadLucideIcon(name: string): Promise<any | null> {
  return getLucideIcon(name);
}

/**
 * Synchronous check whether an icon name exists in the lucide set.
 */
export function hasLucideIcon(name: string): boolean {
  if (!name) return false;
  return _icons.has(name) || _icons.has(kebabToPascal(name));
}
