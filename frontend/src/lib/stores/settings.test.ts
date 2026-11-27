import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

// Mock $app/env so `browser` is true (jsdom) and we control localStorage.
vi.mock('$app/env', () => ({ browser: true, dev: false }));

import {
  accentColors,
  accentColor,
  activeIconPack,
  themeMode,
  showFrontmatter,
  showTrash,
  showHiddenFiles,
  writeInObsidian,
  use24HourClock,
  hideTagsLine,
  devMode,
  folderMetaStore,
  updateFolderMeta,
  initTheme,
  getContrastColor,
  getComplementaryColor,
  hexToRgb,
  getLuminance,
  contrastRatio,
  ensureContrast,
  mixHex,
  rotateHue,
  derivePalette,
  getAccentWarnings,
  MIN_CONTRAST_UI,
  MIN_CONTRAST_TEXT,
  MAX_COLORS,
} from './settings';

function clearStorage() {
  localStorage.clear();
}

describe('settings store — initial values', () => {
  beforeEach(() => clearStorage());

  it('accentColors starts with the default color', () => {
    expect(get(accentColors)).toEqual(['#c8a96e']);
  });

  it('accentColor (derived) starts with the default primary', () => {
    expect(get(accentColor)).toBe('#c8a96e');
  });

  it('activeIconPack defaults to lucide', () => {
    expect(get(activeIconPack)).toBe('lucide');
  });

  it('themeMode defaults to dark', () => {
    expect(get(themeMode)).toBe('dark');
  });

  it('showTrash defaults to true, others false', () => {
    expect(get(showTrash)).toBe(true);
    expect(get(showFrontmatter)).toBe(false);
    expect(get(showHiddenFiles)).toBe(false);
    expect(get(writeInObsidian)).toBe(false);
  });

  it('use24HourClock defaults to true, hideTagsLine true', () => {
    expect(get(use24HourClock)).toBe(true);
    expect(get(hideTagsLine)).toBe(true);
  });

  it('devMode defaults to false when nothing stored', () => {
    expect(get(devMode)).toBe(false);
  });

  it('MAX_COLORS is 3', () => {
    expect(MAX_COLORS).toBe(3);
  });
});

describe('color helpers', () => {
  it('hexToRgb parses a hex string', () => {
    expect(hexToRgb('#ff8800')).toEqual([255, 136, 0]);
  });

  it('hexToRgb returns [0,0,0] for invalid input', () => {
    expect(hexToRgb('nope')).toEqual([0, 0, 0]);
  });

  it('getLuminance returns a number in [0,1]', () => {
    expect(getLuminance(255, 255, 255)).toBeCloseTo(1, 2);
    expect(getLuminance(0, 0, 0)).toBeCloseTo(0, 2);
  });

  it('getContrastColor returns black for light colors, white for dark', () => {
    expect(getContrastColor('#ffffff')).toBe('#000000');
    expect(getContrastColor('#000000')).toBe('#ffffff');
  });
});

describe('accentColors store', () => {
  beforeEach(() => clearStorage());

  it('init() loads saved colors from localStorage and applies them', () => {
    localStorage.setItem('joidy-accent-colors', JSON.stringify(['#ff0000', '#00ff00']));
    accentColors.init();
    expect(get(accentColors)).toEqual(['#ff0000', '#00ff00']);
    // CSS variables applied to documentElement
    expect(document.documentElement.style.getPropertyValue('--accent')).toBe('#ff0000');
    expect(document.documentElement.style.getPropertyValue('--accent-contrast')).toBeDefined();
    expect(document.documentElement.style.getPropertyValue('--accent-contrast').length).toBeGreaterThan(0);
  });

  it('getComplementaryColor rotates hue to provide contrast', () => {
    const comp = getComplementaryColor('#ff0000'); // red hue 0 -> cyan hue 180
    expect(comp).toMatch(/^#[0-9a-fA-F]{6}$/);
    expect(comp).not.toBe('#ff0000');
  });

  it('init() falls back to defaults for invalid stored data', () => {
    localStorage.setItem('joidy-accent-colors', JSON.stringify(['bad', 'data']));
    accentColors.init();
    expect(get(accentColors)).toEqual(['#c8a96e']);
  });

  it('setColor updates a color and persists', () => {
    accentColors.init();
    accentColors.setColor(0, '#123456');
    expect(get(accentColors)[0]).toBe('#123456');
    expect(JSON.parse(localStorage.getItem('joidy-accent-colors')!)[0]).toBe('#123456');
  });

  it('setColor ignores invalid hex', () => {
    accentColors.init();
    const before = get(accentColors)[0];
    accentColors.setColor(0, 'not-a-color');
    expect(get(accentColors)[0]).toBe(before);
  });

  it('addColor appends up to MAX_COLORS', () => {
    accentColors.init();
    expect(get(accentColors).length).toBe(1);
    accentColors.addColor();
    expect(get(accentColors).length).toBe(2);
    accentColors.addColor();
    expect(get(accentColors).length).toBe(3);
    accentColors.addColor();
    expect(get(accentColors).length).toBe(3); // capped
  });

  it('removeColor removes until one remains', () => {
    accentColors.init();
    accentColors.addColor();
    accentColors.removeColor(0);
    expect(get(accentColors).length).toBe(1);
    accentColors.removeColor(0);
    expect(get(accentColors).length).toBe(1); // never empty
  });
});

describe('activeIconPack store', () => {
  beforeEach(() => clearStorage());

  it('init() loads saved icon pack', () => {
    localStorage.setItem('joidy-icon-pack', 'phosphor');
    activeIconPack.init();
    expect(get(activeIconPack)).toBe('phosphor');
  });

  it('set() persists and updates', () => {
    activeIconPack.set('material');
    expect(get(activeIconPack)).toBe('material');
    expect(localStorage.getItem('joidy-icon-pack')).toBe('material');
  });
});

describe('themeMode store (#1270)', () => {
  beforeEach(() => clearStorage());

  it('set persists to the single joidy-theme-mode key', () => {
    themeMode.set('light');
    expect(get(themeMode)).toBe('light');
    expect(localStorage.getItem('joidy-theme-mode')).toBe('light');
  });

  it('toggle flips the mode and persists it', () => {
    themeMode.set('dark');
    themeMode.toggle();
    expect(get(themeMode)).toBe('light');
    expect(localStorage.getItem('joidy-theme-mode')).toBe('light');
    themeMode.toggle();
    expect(get(themeMode)).toBe('dark');
    expect(localStorage.getItem('joidy-theme-mode')).toBe('dark');
  });

  it('migrates the legacy joidy-dark-mode key on first init', async () => {
    localStorage.setItem('joidy-dark-mode', 'false');
    vi.resetModules();
    const fresh = await import('./settings');
    // First subscription triggers lazy init + migration.
    expect(get(fresh.themeMode)).toBe('light');
    expect(localStorage.getItem('joidy-theme-mode')).toBe('light');
    expect(localStorage.getItem('joidy-dark-mode')).toBeNull();
  });

  it('migrates legacy joidy-dark-mode=true to dark', async () => {
    localStorage.setItem('joidy-dark-mode', 'true');
    vi.resetModules();
    const fresh = await import('./settings');
    expect(get(fresh.themeMode)).toBe('dark');
    expect(localStorage.getItem('joidy-theme-mode')).toBe('dark');
    expect(localStorage.getItem('joidy-dark-mode')).toBeNull();
  });

  it('an explicit joidy-theme-mode value wins over the legacy key', async () => {
    localStorage.setItem('joidy-theme-mode', 'light');
    localStorage.setItem('joidy-dark-mode', 'true');
    vi.resetModules();
    const fresh = await import('./settings');
    expect(get(fresh.themeMode)).toBe('light');
    // Legacy key is left untouched when no migration is needed.
    expect(localStorage.getItem('joidy-dark-mode')).toBe('true');
  });

  it('showFrontmatter.set persists', () => {
    showFrontmatter.set(true);
    expect(get(showFrontmatter)).toBe(true);
    expect(localStorage.getItem('joidy-show-frontmatter')).toBe('true');
  });
});

describe('initTheme', () => {
  beforeEach(() => clearStorage());

  it('applies dark theme attribute when themeMode is dark', () => {
    themeMode.set('dark');
    const unsub = initTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    unsub?.();
  });

  it('applies light theme attribute when themeMode is light', () => {
    themeMode.set('light');
    const unsub = initTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    unsub?.();
  });

  it('updates the attribute reactively when themeMode changes', () => {
    themeMode.set('dark');
    const unsub = initTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    themeMode.set('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    unsub?.();
  });
});

describe('devMode store', () => {
  beforeEach(() => clearStorage());

  it('enable() sets and persists true', () => {
    devMode.enable();
    expect(get(devMode)).toBe(true);
    expect(localStorage.getItem('joidy-dev-mode')).toBe('true');
  });

  it('disable() sets and persists false', () => {
    devMode.disable();
    expect(get(devMode)).toBe(false);
    expect(localStorage.getItem('joidy-dev-mode')).toBe('false');
  });

  it('toggle() flips the value', () => {
    devMode.disable();
    devMode.toggle();
    expect(get(devMode)).toBe(true);
    devMode.toggle();
    expect(get(devMode)).toBe(false);
  });

  it('init() reads the saved value', () => {
    localStorage.setItem('joidy-dev-mode', 'true');
    devMode.init();
    expect(get(devMode)).toBe(true);
  });
});

describe('derived palette (#1655)', () => {
  beforeEach(() => clearStorage());

  it('contrastRatio matches WCAG: black/white is 21:1', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 0);
    expect(contrastRatio('#ffffff', '#ffffff')).toBeCloseTo(1, 2);
  });

  it('ensureContrast lifts a dark-on-dark color above the floor', () => {
    const fixed = ensureContrast('#111111', '#000000', MIN_CONTRAST_UI);
    expect(contrastRatio(fixed, '#000000')).toBeGreaterThanOrEqual(MIN_CONTRAST_UI);
  });

  it('ensureContrast darkens a light-on-light color', () => {
    const fixed = ensureContrast('#eeeeee', '#ffffff', MIN_CONTRAST_UI);
    expect(contrastRatio(fixed, '#ffffff')).toBeGreaterThanOrEqual(MIN_CONTRAST_UI);
  });

  it('ensureContrast keeps already-passing colors untouched', () => {
    expect(ensureContrast('#c8a96e', '#000000', MIN_CONTRAST_UI)).toBe('#c8a96e');
  });

  it('mixHex interpolates endpoints and midpoint', () => {
    expect(mixHex('#000000', '#ffffff', 0)).toBe('#000000');
    expect(mixHex('#000000', '#ffffff', 1)).toBe('#ffffff');
    expect(mixHex('#000000', '#ffffff', 0.5)).toBe('#808080');
  });

  it('rotateHue turns red by 120° into green', () => {
    const [r, g, b] = hexToRgb(rotateHue('#ff0000', 120));
    expect(g).toBeGreaterThan(r);
    expect(g).toBeGreaterThan(b);
  });

  it('derivePalette emits the full token set for dark theme', () => {
    const p = derivePalette(['#c8a96e'], 'dark');
    for (const token of [
      '--accent',
      '--accent-gradient',
      '--accent-contrast',
      '--accent-contrast-text',
      '--xp',
      '--xp-2',
      '--xp-3',
      '--xp-dark',
      '--xp-text',
      '--xp-2-text',
      '--xp-3-text',
      '--xp-contrast-text',
      '--success',
      '--warning',
      '--error',
      '--info',
      '--link',
      '--today',
      '--target',
      '--plant',
      '--plant-secondary',
      '--plant-tertiary',
      '--chart-1',
      '--chart-2',
      '--chart-3',
      '--chart-4',
      '--chart-5',
      '--chart-6',
    ]) {
      expect(p[token], token).toMatch(/^#[0-9a-f]{6}$|^linear-gradient/);
    }
  });

  it('with a single pick, secondary/tertiary are derived tints of the primary', () => {
    const p = derivePalette(['#c8a96e'], 'dark');
    expect(p['--xp-2']).not.toBe(p['--xp']);
    expect(p['--xp-3']).not.toBe(p['--xp-2']);
  });

  it('every derived token meets its contrast floor vs the dark background', () => {
    const p = derivePalette(['#111111', '#1a1a1a', '#222222'], 'dark');
    for (const token of ['--xp', '--xp-2', '--xp-3', '--accent-contrast', '--chart-1', '--chart-4']) {
      expect(contrastRatio(p[token], '#000000'), token).toBeGreaterThanOrEqual(MIN_CONTRAST_UI);
    }
    for (const token of ['--xp-text', '--xp-2-text', '--xp-3-text', '--success', '--warning', '--error']) {
      expect(contrastRatio(p[token], '#000000'), token).toBeGreaterThanOrEqual(MIN_CONTRAST_TEXT);
    }
  });

  it('every derived token meets its contrast floor vs the light background', () => {
    const p = derivePalette(['#ffffff', '#eeeeee', '#f5f5f5'], 'light');
    for (const token of ['--xp', '--xp-2', '--xp-3', '--accent-contrast', '--chart-2', '--chart-5']) {
      expect(contrastRatio(p[token], '#ffffff'), token).toBeGreaterThanOrEqual(MIN_CONTRAST_UI);
    }
    for (const token of ['--xp-text', '--xp-2-text', '--xp-3-text', '--error', '--link']) {
      expect(contrastRatio(p[token], '#ffffff'), token).toBeGreaterThanOrEqual(MIN_CONTRAST_TEXT);
    }
  });

  it('dark and light themes derive different tokens for the same picks', () => {
    const dark = derivePalette(['#888888'], 'dark');
    const light = derivePalette(['#888888'], 'light');
    // #888888 vs black = 5.3 (passes), vs white = 3.9 < 4.5 (darkened)
    expect(dark['--xp-text']).not.toBe(light['--xp-text']);
    expect(dark['--xp-dark']).not.toBe(light['--xp-dark']);
  });

  it('getAccentWarnings flags low-contrast picks without blocking them', () => {
    const warnings = getAccentWarnings(['#111111', '#c8a96e', '#00ff00'], 'dark');
    expect(warnings.map((w) => w.index)).toEqual([0]);
    expect(warnings[0].ratio).toBeLessThan(MIN_CONTRAST_UI);
    expect(getAccentWarnings(['#c8a96e'], 'dark')).toEqual([]);
    expect(getAccentWarnings(['#eeeeee'], 'light').length).toBe(1);
  });

  it('applyColors re-derives when the theme flips', () => {
    localStorage.setItem('joidy-accent-colors', JSON.stringify(['#111111']));
    themeMode.set('dark');
    accentColors.init();
    const darkXp = document.documentElement.style.getPropertyValue('--xp');
    themeMode.set('light');
    const lightXp = document.documentElement.style.getPropertyValue('--xp');
    expect(lightXp).not.toBe(darkXp);
    expect(contrastRatio(darkXp, '#000000')).toBeGreaterThanOrEqual(MIN_CONTRAST_UI);
    expect(contrastRatio(lightXp, '#ffffff')).toBeGreaterThanOrEqual(MIN_CONTRAST_UI);
    themeMode.set('dark');
  });
});

describe('folderMetaStore', () => {
  beforeEach(() => clearStorage());

  it('updateFolderMeta adds and persists metadata', () => {
    updateFolderMeta('/vault/notes', { icon: 'Folder', color: '#ff0000' });
    expect(get(folderMetaStore)['/vault/notes']).toEqual({ icon: 'Folder', color: '#ff0000' });
    const stored = JSON.parse(localStorage.getItem('joidy-folder-meta')!);
    expect(stored['/vault/notes']).toEqual({ icon: 'Folder', color: '#ff0000' });
  });
});
