import { writable, derived } from 'svelte/store';
import { browser } from '$app/env';
import { DEFAULT_CLOCK_STYLE, isClockStyleId, type ClockStyleId } from '$lib/utils/clock';
import { loadUserSettings, patchUserSettings } from '$lib/utils/userSettings';
import { SESSION_RESET_EVENT } from './session';

const COLORS_KEY = 'joidy-accent-colors';
const DEFAULT_COLORS = ['#c8a96e'];
const MAX_COLORS = 3;

function isValidHex(v: string) {
  return /^#[0-9a-fA-F]{6}$/.test(v);
}

function hexToRgb(hex: string): [number, number, number] {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? [parseInt(result[1], 16), parseInt(result[2], 16), parseInt(result[3], 16)]
    : [0, 0, 0];
}

function getLuminance(r: number, g: number, b: number): number {
  const [rs, gs, bs] = [r / 255, g / 255, b / 255].map((v) =>
    v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)
  );
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

function getContrastColor(hex: string): string {
  const [r, g, b] = hexToRgb(hex);
  const luminance = getLuminance(r, g, b);
  return luminance > 0.179 ? '#000000' : '#ffffff';
}

function rgbToHsl(r: number, g: number, b: number): [number, number, number] {
  r /= 255;
  g /= 255;
  b /= 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;

  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r:
        h = (g - b) / d + (g < b ? 6 : 0);
        break;
      case g:
        h = (b - r) / d + 2;
        break;
      case b:
        h = (r - g) / d + 4;
        break;
    }
    h /= 6;
  }

  return [Math.round(h * 360), Math.round(s * 100), Math.round(l * 100)];
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  h = ((h % 360) + 360) % 360;
  s = Math.max(0, Math.min(100, s)) / 100;
  l = Math.max(0, Math.min(100, l)) / 100;

  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  let r = 0;
  let g = 0;
  let b = 0;

  if (h < 60) {
    r = c;
    g = x;
    b = 0;
  } else if (h < 120) {
    r = x;
    g = c;
    b = 0;
  } else if (h < 180) {
    r = 0;
    g = c;
    b = x;
  } else if (h < 240) {
    r = 0;
    g = x;
    b = c;
  } else if (h < 300) {
    r = x;
    g = 0;
    b = c;
  } else {
    r = c;
    g = 0;
    b = x;
  }

  return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)];
}

function rgbToHex(rgb: [number, number, number]): string {
  const toHex = (n: number) =>
    Math.max(0, Math.min(255, Math.round(n)))
      .toString(16)
      .padStart(2, '0');
  return `#${toHex(rgb[0])}${toHex(rgb[1])}${toHex(rgb[2])}`;
}

function getComplementaryColor(hex: string): string {
  if (!isValidHex(hex)) return '#f59e0b';
  const [r, g, b] = hexToRgb(hex);
  const [h, s, l] = rgbToHsl(r, g, b);

  // Rotate hue by 180 degrees for complementary contrast
  const compH = (h + 180) % 360;
  // Ensure enough saturation and pleasant lightness for contrast against dark UI backgrounds
  const compS = s < 30 ? 80 : Math.min(95, Math.max(65, s));
  const compL = Math.min(72, Math.max(52, l));

  return rgbToHex(hslToRgb(compH, compS, compL));
}

// ── Derived accent palette (#1655) ──────────────────────────────────────────
// The 3 picked colors are the raw input; everything the UI consumes is a
// derived token computed against the active theme background so blends,
// tints and semantic colors stay coherent — and contrast-safe — in both
// dark and light mode.
export type PaletteTheme = 'light' | 'dark';

// WCAG contrast floors: 4.5:1 for text-adjacent tokens, 3:1 for large/UI
// elements (fills, strokes, borders, chart series).
export const MIN_CONTRAST_TEXT = 4.5;
export const MIN_CONTRAST_UI = 3;

const THEME_SURFACES: Record<PaletteTheme, { bg: string; surface: string; text: string }> = {
  dark: { bg: '#000000', surface: '#000000', text: '#ffffff' },
  light: { bg: '#ffffff', surface: '#ffffff', text: '#000000' },
};

/** WCAG 2.x contrast ratio between two hex colors (1–21). */
function contrastRatio(hexA: string, hexB: string): number {
  const [r1, g1, b1] = hexToRgb(hexA);
  const [r2, g2, b2] = hexToRgb(hexB);
  const l1 = getLuminance(r1, g1, b1);
  const l2 = getLuminance(r2, g2, b2);
  const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * Nudge a color's lightness until it reaches `minRatio` against `bgHex`.
 * Lightens on dark backgrounds, darkens on light ones; hue and saturation
 * are preserved so the derived color keeps the user's pick recognizable.
 */
function ensureContrast(hex: string, bgHex: string, minRatio: number): string {
  if (!isValidHex(hex) || !isValidHex(bgHex)) return hex;
  if (contrastRatio(hex, bgHex) >= minRatio) return hex;
  const [r, g, b] = hexToRgb(hex);
  const [h, s, startL] = rgbToHsl(r, g, b);
  const bgLum = getLuminance(...hexToRgb(bgHex));
  const dir = bgLum < 0.18 ? 1 : -1;
  for (let i = 0; i < 50; i++) {
    const l = Math.max(0, Math.min(100, startL + dir * i * 2));
    const candidate = rgbToHex(hslToRgb(h, s, l));
    if (contrastRatio(candidate, bgHex) >= minRatio) return candidate;
    if (l === 0 || l === 100) break;
  }
  return dir > 0 ? '#ffffff' : '#000000';
}

/** Linear RGB interpolation between two hex colors. `t=0` → a, `t=1` → b. */
function mixHex(a: string, b: string, t: number): string {
  const [r1, g1, b1] = hexToRgb(a);
  const [r2, g2, b2] = hexToRgb(b);
  return rgbToHex([r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t]);
}

/** Rotate a color's hue by `deg` degrees, keeping saturation/lightness. */
function rotateHue(hex: string, deg: number): string {
  const [r, g, b] = hexToRgb(hex);
  const [h, s, l] = rgbToHsl(r, g, b);
  return rgbToHex(hslToRgb(h + deg, s, l));
}

/** Move `from` toward `to` along the shortest hue arc by `t` (0–1). */
function lerpHue(from: number, to: number, t: number): number {
  const d = ((to - from + 540) % 360) - 180;
  return (((from + d * t) % 360) + 360) % 360;
}

/** Circular mean of a set of hues (degrees). */
function meanHue(hues: number[]): number {
  if (hues.length === 0) return 0;
  let x = 0;
  let y = 0;
  for (const h of hues) {
    x += Math.cos((h * Math.PI) / 180);
    y += Math.sin((h * Math.PI) / 180);
  }
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

// Canonical semantic hues stay recognizable (green = success, red = error…)
// but are harmonized toward the accent trio's hue/saturation center, then
// contrast-floored — so semantics read as "from the same palette" (#1655).
const SEMANTIC_BASES: Record<string, string> = {
  '--success': '#10b981',
  '--warning': '#f59e0b',
  '--error': '#ef4444',
  '--info': '#06b6d4',
  '--link': '#3b82f6',
  '--today': '#fbbf24',
  '--target': '#10b981',
};

/**
 * Compute every derived accent token for `theme` from the user's base colors.
 * Returns a `--token → value` map for `documentElement.style`. Pure function —
 * DOM access lives in applyColors().
 */
export function derivePalette(colors: string[], theme: PaletteTheme = 'dark'): Record<string, string> {
  const { bg, surface, text } = THEME_SURFACES[theme];
  const primary = colors[0] ?? DEFAULT_COLORS[0];
  // Fewer than 3 picks: derive the missing voices as tints/shades of the
  // primary mixed toward the theme text color (≈ previous color-mix fallback).
  const secondary = colors[1] ?? mixHex(primary, text, 0.3);
  const tertiary = colors[2] ?? mixHex(secondary, text, 0.3);
  const trio = [primary, secondary, tertiary];

  // Base trio floored at UI-element contrast so accents never vanish.
  const xp = ensureContrast(primary, surface, MIN_CONTRAST_UI);
  const xp2 = ensureContrast(secondary, surface, MIN_CONTRAST_UI);
  const xp3 = ensureContrast(tertiary, surface, MIN_CONTRAST_UI);

  // Text-adjacent variants floored at WCAG AA text contrast.
  const xpText = ensureContrast(primary, bg, MIN_CONTRAST_TEXT);
  const xp2Text = ensureContrast(secondary, bg, MIN_CONTRAST_TEXT);
  const xp3Text = ensureContrast(tertiary, bg, MIN_CONTRAST_TEXT);

  const contrastText = getContrastColor(xp);

  // Hue/saturation center of the trio — the harmonization target for
  // semantic colors so they feel derived, not hardcoded.
  const hsls = trio.map((c) => rgbToHsl(...hexToRgb(c)));
  const trioHue = meanHue(hsls.map(([h]) => h));
  const trioSat = hsls.reduce((acc, [, s]) => acc + s, 0) / hsls.length;

  const harmonized = (canonical: string): string => {
    const [h, s, l] = rgbToHsl(...hexToRgb(canonical));
    const hue = lerpHue(h, trioHue, 0.2);
    const sat = s + (trioSat - s) * 0.3;
    return ensureContrast(rgbToHex(hslToRgb(hue, sat, l)), surface, MIN_CONTRAST_TEXT);
  };

  const palette: Record<string, string> = {
    '--accent': xp,
    '--accent-gradient': computeGradient([xp, xp2, xp3]),
    '--accent-contrast': ensureContrast(getComplementaryColor(primary), bg, MIN_CONTRAST_UI),
    '--accent-contrast-text': contrastText,
    '--xp': xp,
    '--xp-2': xp2,
    '--xp-3': xp3,
    // Dark shade of the primary — used for gradient ends / deep accents.
    '--xp-dark': mixHex(xp, bg, 0.4),
    '--xp-text': xpText,
    '--xp-2-text': xp2Text,
    '--xp-3-text': xp3Text,
    '--xp-contrast-text': contrastText,
    '--plant': xp,
    '--plant-secondary': xp2,
    '--plant-tertiary': xp3,
    '--plant-glow': xp2,
    '--plant-2': xp2,
    '--plant-3': xp3,
  };

  for (const [token, canonical] of Object.entries(SEMANTIC_BASES)) {
    palette[token] = harmonized(canonical);
  }

  // Chart/series palette: the trio plus a hue-rotated counterpart of each —
  // six distinguishable series all sourced from the user's picks.
  for (let i = 0; i < 6; i++) {
    const base = trio[i % 3];
    const src = i < 3 ? base : rotateHue(base, 140);
    palette[`--chart-${i + 1}`] = ensureContrast(src, surface, MIN_CONTRAST_UI);
  }

  return palette;
}

/**
 * Indices of picked colors whose contrast against the active theme background
 * falls below the UI-element floor. Used by Settings to warn — never block.
 */
export function getAccentWarnings(
  colors: string[],
  theme: PaletteTheme
): { index: number; ratio: number }[] {
  const { bg } = THEME_SURFACES[theme];
  return colors
    .map((c, i) => ({ index: i, ratio: contrastRatio(c, bg) }))
    .filter((w) => w.ratio < MIN_CONTRAST_UI);
}

function activePaletteTheme(): PaletteTheme {
  if (!browser) return 'dark';
  return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
}

export { getContrastColor, getComplementaryColor, hexToRgb, getLuminance, rgbToHsl, hslToRgb };
export { contrastRatio, ensureContrast, mixHex, rotateHue };

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
  if (!browser) return [...DEFAULT_COLORS];
  try {
    const saved = localStorage.getItem(COLORS_KEY);
    if (saved) {
      const parsed: unknown = JSON.parse(saved);
      return normalizeColors(parsed);
    }
  } catch {
    /* ignore */
  }
  return [...DEFAULT_COLORS];
}

function persist(colors: string[]) {
  if (browser) {
    localStorage.setItem(COLORS_KEY, JSON.stringify(colors));
  }
}

// Last applied picks — kept so the palette can be re-derived when the theme
// flips without re-reading the store (module-level subscription below).
let lastAppliedColors: string[] | null = null;

function applyColors(colors: string[]) {
  if (!browser) return;
  lastAppliedColors = [...colors];
  const palette = derivePalette(colors, activePaletteTheme());
  for (const [token, value] of Object.entries(palette)) {
    document.documentElement.style.setProperty(token, value);
  }
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
      update((prev) => {
        if (index < 0 || index >= prev.length) return prev;
        const next = [...prev];
        next[index] = color;
        persist(next);
        applyColors(next);
        return next;
      });
    },

    addColor() {
      update((prev) => {
        if (prev.length >= MAX_COLORS) return prev;
        const next = [...prev, prev[prev.length - 1]];
        persist(next);
        applyColors(next);
        return next;
      });
    },

    removeColor(index: number) {
      update((prev) => {
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
  subscribe: derived(accentColors, (c) => c[0]).subscribe,
  init: () => accentColors.init(),
};

export type IconPack = 'lucide' | 'phosphor' | 'material';

function createIconPackStore() {
  // Start with 'lucide' for SSR — set() applies the real value client-side
  const { subscribe, set } = writable<IconPack>('lucide');
  return {
    subscribe,
    init() {
      if (browser) {
        const saved = (localStorage.getItem('joidy-icon-pack') as IconPack) || 'lucide';
        set(saved);
      }
    },
    set: (val: IconPack) => {
      if (browser) localStorage.setItem('joidy-icon-pack', val);
      set(val);
    },
  };
}
export const activeIconPack = createIconPackStore();

function createBooleanStore(key: string, defaultValue: boolean = false) {
  // Start with defaultValue for SSR — read localStorage only client-side
  const { subscribe, set, update } = writable<boolean>(defaultValue);
  let _initialized = false;
  function ensureInit() {
    if (_initialized || !browser) return;
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
      if (browser) localStorage.setItem(key, String(val));
      set(val);
    },
    toggle: () =>
      update((v) => {
        ensureInit();
        const next = !v;
        if (browser) localStorage.setItem(key, String(next));
        return next;
      }),
  };
}

export const showFrontmatter = createBooleanStore('joidy-show-frontmatter', false);
export const showTrash = createBooleanStore('joidy-show-trash', true);
export const showHiddenFiles = createBooleanStore('joidy-show-hidden', false);
export const writeInObsidian = createBooleanStore('joidy-write-obsidian', false);
export const use24HourClock = createBooleanStore('joidy-use-24h-clock', true);
export const hideTagsLine = createBooleanStore('joidy-hide-tags-line', true);

// ── Clock style (#707) ───────────────────────────────────────────────────────
// Persisted inside the shared `joidy-user-settings-v1` blob via userSettings
// (`appearance.clockStyle`), so it survives reloads like the other UI prefs.
function loadClockStyle(): ClockStyleId {
  if (!browser) return DEFAULT_CLOCK_STYLE;
  const saved = loadUserSettings().appearance?.clockStyle;
  return isClockStyleId(saved) ? saved : DEFAULT_CLOCK_STYLE;
}

function createClockStyleStore() {
  const { subscribe, set } = writable<ClockStyleId>(DEFAULT_CLOCK_STYLE);
  let _initialized = false;

  function ensureInit() {
    if (_initialized || !browser) return;
    _initialized = true;
    set(loadClockStyle());
  }

  return {
    subscribe: (run: (v: ClockStyleId) => void, invalidate?: () => void) => {
      ensureInit();
      return subscribe(run, invalidate);
    },
    set: (val: ClockStyleId) => {
      _initialized = true;
      if (!isClockStyleId(val)) return;
      patchUserSettings({ appearance: { clockStyle: val } });
      set(val);
    },
    init: () => {
      _initialized = true;
      set(loadClockStyle());
    },
  };
}

export const clockStyle = createClockStyleStore();

// ── Theme mode (#1270) ───────────────────────────────────────────────────────
// Single source of truth for the color theme. Replaces the old `darkMode`
// boolean store (`joidy-dark-mode`), which competed with this one: both wrote
// `data-theme`, and `darkMode` always won at boot — so the Settings "light"
// choice silently reverted on every reload while the palette toggle flipped
// the UI without updating the Settings radios.
export type ThemeMode = 'light' | 'dark';
const THEME_MODE_KEY = 'joidy-theme-mode';
const LEGACY_DARK_MODE_KEY = 'joidy-dark-mode';

function loadThemeMode(): ThemeMode {
  if (!browser) return 'dark';
  const raw = localStorage.getItem(THEME_MODE_KEY);
  if (raw === 'light' || raw === 'dark') return raw;
  // Migrate the legacy boolean key: 'false' meant light mode, anything else
  // (including 'true') meant dark. Remove it so only one key survives.
  const legacy = localStorage.getItem(LEGACY_DARK_MODE_KEY);
  if (legacy !== null) {
    const migrated: ThemeMode = legacy === 'false' ? 'light' : 'dark';
    localStorage.setItem(THEME_MODE_KEY, migrated);
    localStorage.removeItem(LEGACY_DARK_MODE_KEY);
    return migrated;
  }
  return 'dark';
}

function createThemeModeStore() {
  const { subscribe, set, update } = writable<ThemeMode>('dark');
  let _initialized = false;

  function applyMode(mode: ThemeMode) {
    if (!browser) return;
    document.documentElement.setAttribute('data-theme', mode);
  }

  function ensureInit() {
    if (_initialized || !browser) return;
    _initialized = true;
    const saved = loadThemeMode();
    set(saved);
    applyMode(saved);
  }

  return {
    subscribe: (run: (v: ThemeMode) => void, invalidate?: () => void) => {
      ensureInit();
      return subscribe(run, invalidate);
    },
    set: (val: ThemeMode) => {
      _initialized = true;
      if (browser) localStorage.setItem(THEME_MODE_KEY, val);
      applyMode(val);
      set(val);
    },
    toggle: () => {
      ensureInit();
      update((v) => {
        const next: ThemeMode = v === 'dark' ? 'light' : 'dark';
        if (browser) localStorage.setItem(THEME_MODE_KEY, next);
        applyMode(next);
        return next;
      });
    },
    init: ensureInit,
  };
}

export const themeMode = createThemeModeStore();

// Re-derive the accent palette whenever the theme flips so contrast-floored
// and harmonized tokens stay correct against the new background (#1655).
if (browser) {
  themeMode.subscribe(() => {
    if (lastAppliedColors) applyColors(lastAppliedColors);
  });
}

export function initTheme(): (() => void) | void {
  // Return the unsubscribe function so the caller can clean it up.
  // Previously the subscription was auto-unsubscribed immediately via `()`,
  // which meant theme changes after init were never applied (#265).
  // Subscribing also triggers the store's lazy init/migration (#1270).
  return themeMode.subscribe((mode) => {
    if (browser) {
      document.documentElement.setAttribute('data-theme', mode);
    }
  });
}

export interface FolderMeta {
  icon: string;
  color: string;
}
type FolderMetaMap = Record<string, FolderMeta>;
const FOLDER_META_KEY = 'joidy-folder-meta';

function loadFolderMeta(): FolderMetaMap {
  if (!browser) return {};
  try {
    const raw = localStorage.getItem(FOLDER_META_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function persistFolderMeta(meta: FolderMetaMap) {
  if (browser) {
    localStorage.setItem(FOLDER_META_KEY, JSON.stringify(meta));
  }
}

export const folderMetaStore = writable<FolderMetaMap>(loadFolderMeta());

export function updateFolderMeta(path: string, meta: FolderMeta) {
  folderMetaStore.update((m) => {
    const next = { ...m, [path]: meta };
    persistFolderMeta(next);
    return next;
  });
}

// The `joidy-folder-meta` key is wiped on session reset (logout / 401) since
// it maps the user's vault folder paths (#1325) — mirror that in memory so a
// later updateFolderMeta() cannot re-persist the previous user's paths.
if (browser) {
  window.addEventListener(SESSION_RESET_EVENT, () => folderMetaStore.set({}));
}

// ── Developer Mode ───────────────────────────────────────────────────────────
const DEV_MODE_KEY = 'joidy-dev-mode';

function loadDevMode(): boolean {
  if (!browser) return false;
  return localStorage.getItem(DEV_MODE_KEY) === 'true';
}

function persistDevMode(enabled: boolean) {
  if (!browser) return;
  localStorage.setItem(DEV_MODE_KEY, String(enabled));
}

function createDevModeStore() {
  const { subscribe, set, update } = writable<boolean>(loadDevMode());

  return {
    subscribe,
    enable: () => {
      persistDevMode(true);
      set(true);
    },
    disable: () => {
      persistDevMode(false);
      set(false);
    },
    toggle: () => {
      update((v) => {
        const newVal = !v;
        persistDevMode(newVal);
        return newVal;
      });
    },
    init: () => set(loadDevMode()),
  };
}

export const devMode = createDevModeStore();

export { MAX_COLORS };
