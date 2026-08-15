// Tree-shakeable access to the lucide-svelte icon set.
//
// Uses `import.meta.glob` with `eager: false` so that:
//   - `ALL_LUCIDE_ICON_NAMES` is available synchronously (only the file paths
//     are enumerated, no icon code is imported).
//   - `loadLucideIcon()` triggers a per-icon dynamic import, letting Vite split
//     each icon into its own chunk instead of bundling them all up front.
//
// The glob targets the compiled `.js` icon files shipped under
// `lucide-svelte/dist/icons/` (the package `./icons/*` export).

// Path is relative to this file: src/lib/utils/ → frontend/node_modules/...
const iconModules = import.meta.glob('../../../node_modules/lucide-svelte/dist/icons/*.js', {
  eager: false,
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

const _iconPaths = Object.keys(iconModules);

// Build a map of PascalCase name → lazy loader function.
const _loaders = new Map<string, () => Promise<any>>();
for (const path of _iconPaths) {
  // path looks like "../../../node_modules/lucide-svelte/dist/icons/a-arrow-down.js"
  const file = path.split('/').pop()!.replace(/\.js$/, '');
  _loaders.set(kebabToPascal(file), iconModules[path] as () => Promise<any>);
}

/**
 * All available lucide icon names in PascalCase (e.g. "Search", "FileText").
 * Used by the icon picker to render its grid without importing any icon code.
 */
export const ALL_LUCIDE_ICON_NAMES: string[] = Array.from(_loaders.keys()).sort();

/**
 * Resolve a loader by either a PascalCase or kebab-case icon name.
 * Returns the loader or undefined when the name does not match any icon.
 */
function getLoader(name: string): (() => Promise<any>) | undefined {
  if (!name) return undefined;
  // Try the name as-is (PascalCase) first, then convert kebab → Pascal.
  return _loaders.get(name) ?? _loaders.get(kebabToPascal(name));
}

/**
 * Lazily import a lucide icon component by name.
 *
 * Accepts either PascalCase ("FileText") or kebab-case ("file-text"). Resolves
 * to the icon's Svelte component, or `null` when the name is unknown so callers
 * can fall back to a placeholder (e.g. `Circle`).
 */
export async function loadLucideIcon(name: string): Promise<any | null> {
  const loader = getLoader(name);
  if (!loader) return null;
  try {
    return await loader();
  } catch {
    return null;
  }
}

/**
 * Synchronous check whether an icon name exists in the lucide set, without
 * importing the icon. Useful for cheap validation before triggering a load.
 */
export function hasLucideIcon(name: string): boolean {
  return getLoader(name) !== undefined;
}
