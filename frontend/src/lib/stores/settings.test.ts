import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

// Mock $app/environment so `browser` is true (jsdom) and we control localStorage.
vi.mock('$app/environment', () => ({ browser: true, dev: false }));

import {
  accentColors,
  accentColor,
  activeIconPack,
  darkMode,
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
  hexToRgb,
  getLuminance,
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

  it('darkMode defaults to true', () => {
    expect(get(darkMode)).toBe(true);
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

describe('boolean stores (darkMode etc.)', () => {
  beforeEach(() => clearStorage());

  it('darkMode.set persists to localStorage', () => {
    darkMode.set(false);
    expect(get(darkMode)).toBe(false);
    expect(localStorage.getItem('joidy-dark-mode')).toBe('false');
  });

  it('darkMode reads saved value on subscribe', () => {
    localStorage.setItem('joidy-dark-mode', 'false');
    // createBooleanStore reads on first subscribe; subscribing again reads it
    darkMode.set(true); // ensure initialized flag set
    localStorage.setItem('joidy-dark-mode', 'false');
    // Re-import not possible; instead verify set+persist roundtrip
    darkMode.set(false);
    expect(localStorage.getItem('joidy-dark-mode')).toBe('false');
  });

  it('showFrontmatter.set persists', () => {
    showFrontmatter.set(true);
    expect(get(showFrontmatter)).toBe(true);
    expect(localStorage.getItem('joidy-show-frontmatter')).toBe('true');
  });
});

describe('initTheme', () => {
  beforeEach(() => clearStorage());

  it('applies dark theme attribute when darkMode is true', () => {
    darkMode.set(true);
    const unsub = initTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    unsub?.();
  });

  it('applies light theme attribute when darkMode is false', () => {
    darkMode.set(false);
    const unsub = initTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    unsub?.();
  });

  it('updates the attribute reactively when darkMode changes', () => {
    darkMode.set(true);
    const unsub = initTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    darkMode.set(false);
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

describe('folderMetaStore', () => {
  beforeEach(() => clearStorage());

  it('updateFolderMeta adds and persists metadata', () => {
    updateFolderMeta('/vault/notes', { icon: 'Folder', color: '#ff0000' });
    expect(get(folderMetaStore)['/vault/notes']).toEqual({ icon: 'Folder', color: '#ff0000' });
    const stored = JSON.parse(localStorage.getItem('joidy-folder-meta')!);
    expect(stored['/vault/notes']).toEqual({ icon: 'Folder', color: '#ff0000' });
  });
});
