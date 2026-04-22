import { writable, derived } from 'svelte/store';

const COLORS_KEY     = 'joidy-accent-colors';
const DEFAULT_COLORS = ['#c8a96e'];
const MAX_COLORS     = 6;

function isValidHex(v: string) {
  return /^#[0-9a-fA-F]{6}$/.test(v);
}

function computeGradient(colors: string[]): string {
  if (colors.length === 1) return colors[0];
  return `linear-gradient(to right, ${colors.join(', ')})`;
}

function loadColors(): string[] {
  if (typeof localStorage === 'undefined') return [...DEFAULT_COLORS];
  try {
    const saved = localStorage.getItem(COLORS_KEY);
    if (saved) {
      const parsed: unknown = JSON.parse(saved);
      if (Array.isArray(parsed) && parsed.length >= 1 && parsed.every(isValidHex)) {
        return parsed as string[];
      }
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
  const primary  = colors[0];
  const gradient = computeGradient(colors);
  document.documentElement.style.setProperty('--xp',              primary);
  document.documentElement.style.setProperty('--plant',           primary);
  document.documentElement.style.setProperty('--plant-glow',      primary);
  document.documentElement.style.setProperty('--accent-gradient', gradient);
}

function createAccentStore() {
  // Start with DEFAULT for SSR — init() applies the real saved value client-side
  const { subscribe, update } = writable<string[]>([...DEFAULT_COLORS]);

  return {
    subscribe,

    init() {
      const saved = loadColors();
      update(() => saved);
      applyColors(saved);
    },

    setColor(index: number, color: string) {
      if (!isValidHex(color)) return;
      update(prev => {
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

export { MAX_COLORS };
