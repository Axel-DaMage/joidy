import { writable, derived } from 'svelte/store';

const COLORS_KEY     = 'joidy-accent-colors';
const DEFAULT_COLORS = ['#c8a96e'];
const MAX_COLORS     = 3;

function isValidHex(v: string) {
  return /^#[0-9a-fA-F]{6}$/.test(v);
}

function hexToRgb(hex: string): [number, number, number] {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? [parseInt(result[1], 16), parseInt(result[2], 16), parseInt(result[3], 16)] : [0, 0, 0];
}

function getLuminance(r: number, g: number, b: number): number {
  const [rs, gs, bs] = [r / 255, g / 255, b / 255].map(v => v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

function getContrastColor(hex: string): string {
  const [r, g, b] = hexToRgb(hex);
  const luminance = getLuminance(r, g, b);
  return luminance > 0.179 ? '#000000' : '#ffffff';
}

export { getContrastColor, hexToRgb, getLuminance };

function computeGradient(colors: string[]): string {
  if (colors.length === 1) return colors[0];
  return `linear-gradient(to right, ${colors.join(', ')})`;
}

function normalizeColors(colors: unknown): string[] {
  if (!Array.isArray(colors)) return [...DEFAULT_COLORS];
  const normalized = colors
    .filter((c): c is string => typeof c === 'string' && isValidHex(c))
    .slice(0, MAX_COLORS);
  return normalized.length >= 1 ? normalized : [...DEFAULT_COLORS];
}

function loadColors(): string[] {
  if (typeof localStorage === 'undefined') return [...DEFAULT_COLORS];
  try {
    const saved = localStorage.getItem(COLORS_KEY);
    if (saved) {
      const parsed: unknown = JSON.parse(saved);
      return normalizeColors(parsed);
    }
  } catch { /* ignore */ }
  return [...DEFAULT_COLORS];
}

function persist(colors: string[]) {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(COLORS_KEY, JSON.stringify(colors));
  }
}

function applyColors(colors: string[]) {
  if (typeof document === 'undefined') return;
  const primary = colors[0];
  const secondary = colors.length > 1 ? colors[1] : `color-mix(in srgb, ${primary} 70%, var(--text-primary))`;
  const tertiary = colors.length > 2 ? colors[2] : `color-mix(in srgb, ${secondary} 70%, var(--text-primary))`;
  
  const secondaryPlain = colors[1] ?? primary;
  const tertiaryPlain = colors[2] ?? secondaryPlain;
  const gradient = computeGradient(colors);

  document.documentElement.style.setProperty('--accent', primary);
  document.documentElement.style.setProperty('--accent-gradient', gradient);

  const contrastText = getContrastColor(primary);
  document.documentElement.style.setProperty('--accent-contrast-text', contrastText);
  document.documentElement.style.setProperty('--xp-contrast-text', contrastText);

  document.documentElement.style.setProperty('--xp', primary);
  document.documentElement.style.setProperty('--xp-2', secondaryPlain);
  document.documentElement.style.setProperty('--xp-3', tertiaryPlain);
  document.documentElement.style.setProperty('--xp-dark', secondaryPlain);

  document.documentElement.style.setProperty('--plant', primary);
  document.documentElement.style.setProperty('--plant-secondary', secondaryPlain);
  document.documentElement.style.setProperty('--plant-tertiary', tertiaryPlain);
  document.documentElement.style.setProperty('--plant-glow', secondaryPlain);
  document.documentElement.style.setProperty('--plant-2', secondaryPlain);
  document.documentElement.style.setProperty('--plant-3', tertiaryPlain);
}

function createAccentStore() {
  // Start with DEFAULT for SSR — init() applies the real saved value client-side
  const { subscribe, update } = writable<string[]>([...DEFAULT_COLORS]);

  return {
    subscribe,

    init() {
      const saved = loadColors();
      update(() => saved);
      persist(saved);
      applyColors(saved);
    },

    setColor(index: number, color: string) {
      if (!isValidHex(color)) return;
      update(prev => {
        if (index < 0 || index >= prev.length) return prev;
        const next = [...prev];
        next[index] = color;
        persist(next);
        applyColors(next);
        return next;
      });
    },

    addColor() {
      update(prev => {
        if (prev.length >= MAX_COLORS) return prev;
        const next = [...prev, prev[prev.length - 1]];
        persist(next);
        applyColors(next);
        return next;
      });
    },

    removeColor(index: number) {
      update(prev => {
        if (prev.length <= 1) return prev;
        const next = prev.filter((_, i) => i !== index);
        persist(next);
        applyColors(next);
        return next;
      });
    },
  };
}

export const accentColors = createAccentStore();

// Single-color convenience (primary accent)
export const accentColor = {
  subscribe: derived(accentColors, c => c[0]).subscribe,
  init: () => accentColors.init(),
};

export type IconPack = 'lucide' | 'phosphor' | 'material';

function createIconPackStore() {
  // Start with 'lucide' for SSR — set() applies the real value client-side
  const { subscribe, set } = writable<IconPack>('lucide');
  return {
    subscribe,
    init() {
      if (typeof localStorage !== 'undefined') {
        const saved = (localStorage.getItem('joidy-icon-pack') as IconPack) || 'lucide';
        set(saved);
      }
    },
    set: (val: IconPack) => {
      if (typeof localStorage !== 'undefined') localStorage.setItem('joidy-icon-pack', val);
      set(val);
    }
  };
}
export const activeIconPack = createIconPackStore();

function createBooleanStore(key: string, defaultValue: boolean = false) {
  // Start with defaultValue for SSR — read localStorage only client-side
  const { subscribe, set, update } = writable<boolean>(defaultValue);
  let _initialized = false;
  function ensureInit() {
    if (_initialized || typeof localStorage === 'undefined') return;
    _initialized = true;
    const saved = localStorage.getItem(key);
    if (saved !== null) set(saved === 'true');
  }
  return {
    subscribe: (run: (v: boolean) => void, invalidate?: () => void) => {
      ensureInit();
      return subscribe(run, invalidate);
    },
    set: (val: boolean) => {
      _initialized = true;
      if (typeof localStorage !== 'undefined') localStorage.setItem(key, String(val));
      set(val);
    },
    toggle: () => update(v => {
      ensureInit();
      const next = !v;
      if (typeof localStorage !== 'undefined') localStorage.setItem(key, String(next));
      return next;
    })
  };
}

export const showFrontmatter = createBooleanStore('joidy-show-frontmatter', false);
export const showTrash       = createBooleanStore('joidy-show-trash', false);
export const showHiddenFiles = createBooleanStore('joidy-show-hidden', false);
export const writeInObsidian = createBooleanStore('joidy-write-obsidian', false);
export const use24HourClock  = createBooleanStore('joidy-use-24h-clock', true);
export const hideTagsLine    = createBooleanStore('joidy-hide-tags-line', true);

export interface FolderMeta { icon: string; color: string; }
type FolderMetaMap = Record<string, FolderMeta>;
const FOLDER_META_KEY = 'joidy-folder-meta';

function loadFolderMeta(): FolderMetaMap {
  if (typeof localStorage === 'undefined') return {};
  try {
    const raw = localStorage.getItem(FOLDER_META_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch { return {}; }
}

function persistFolderMeta(meta: FolderMetaMap) {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(FOLDER_META_KEY, JSON.stringify(meta));
  }
}

export const folderMetaStore = writable<FolderMetaMap>(loadFolderMeta());

export function updateFolderMeta(path: string, meta: FolderMeta) {
  folderMetaStore.update(m => {
    const next = { ...m, [path]: meta };
    persistFolderMeta(next);
    return next;
  });
}

export { MAX_COLORS };
