import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock $app/env so `browser` is true (jsdom) and we control localStorage.
vi.mock('$app/env', () => ({ browser: true, dev: false }));

import {
  prefKey,
  loadPref,
  savePref,
  removePref,
  VIEW_PREF_PREFIX,
} from './persistedState';

beforeEach(() => localStorage.clear());

describe('prefKey', () => {
  it('builds namespaced keys as joidy.<view>.<prop>', () => {
    expect(prefKey('goals', 'tab')).toBe('joidy.goals.tab');
    expect(prefKey('notes', 'sortMode')).toBe('joidy.notes.sortMode');
    expect(prefKey('goals', 'tab').startsWith(VIEW_PREF_PREFIX)).toBe(true);
  });
});

describe('savePref / loadPref round-trip', () => {
  it('persists and restores strings', () => {
    savePref('goals', 'tab', 'planning');
    expect(loadPref('goals', 'tab', 'editor')).toBe('planning');
  });

  it('persists and restores booleans', () => {
    savePref('goals', 'poolOpen', false);
    expect(loadPref('goals', 'poolOpen', true)).toBe(false);
  });

  it('persists and restores null', () => {
    savePref('emails', 'accountFilter', null);
    expect(loadPref<string | null>('emails', 'accountFilter', 'x@y.z')).toBeNull();
  });

  it('persists and restores objects/arrays', () => {
    savePref('notes', 'collapsedPaths', ['a/b', 'c']);
    expect(loadPref('notes', 'collapsedPaths', [])).toEqual(['a/b', 'c']);
  });

  it('returns the fallback when the key is absent', () => {
    expect(loadPref('goals', 'missing', 'def')).toBe('def');
  });

  it('returns the fallback on corrupt JSON', () => {
    localStorage.setItem('joidy.goals.tab', '{oops');
    expect(loadPref('goals', 'tab', 'editor')).toBe('editor');
  });

  it('honors the isValid validator', () => {
    savePref('goals', 'tab', 'bogus');
    const valid = loadPref('goals', 'tab', 'editor', {
      isValid: (v) => ['editor', 'planning'].includes(v as string),
    });
    expect(valid).toBe('editor');
  });

  it('saving undefined removes the key', () => {
    savePref('goals', 'tab', 'inbox');
    savePref('goals', 'tab', undefined);
    expect(loadPref('goals', 'tab', 'editor')).toBe('editor');
  });
});

describe('removePref', () => {
  it('removes the namespaced key', () => {
    savePref('goals', 'tab', 'inbox');
    removePref('goals', 'tab');
    expect(localStorage.getItem('joidy.goals.tab')).toBeNull();
  });
});

describe('legacy migration', () => {
  it('migrates a raw-string legacy key into the namespaced key', () => {
    localStorage.setItem('goals.currentTab', 'inbox');
    const value = loadPref('goals', 'tab', 'editor', { legacyKey: 'goals.currentTab' });
    expect(value).toBe('inbox');
    // Rewritten under the new key as JSON and the legacy key is gone.
    expect(localStorage.getItem('joidy.goals.tab')).toBe('"inbox"');
    expect(localStorage.getItem('goals.currentTab')).toBeNull();
  });

  it('supports custom legacy converters (e.g. "1"/"0" flags)', () => {
    localStorage.setItem('joidy-calendar-tray-collapsed', '1');
    const value = loadPref('calendar', 'trayCollapsed', false, {
      legacyKey: 'joidy-calendar-tray-collapsed',
      legacyFrom: (raw) => raw === '1',
    });
    expect(value).toBe(true);
  });

  it('ignores the legacy key when the namespaced key already exists', () => {
    localStorage.setItem('goals.currentTab', 'inbox');
    savePref('goals', 'tab', 'history');
    expect(loadPref('goals', 'tab', 'editor', { legacyKey: 'goals.currentTab' })).toBe('history');
    // The stale legacy key is left untouched — not the caller's problem.
    expect(localStorage.getItem('goals.currentTab')).toBe('inbox');
  });

  it('rejects migrated values that fail isValid', () => {
    localStorage.setItem('goals.planningView', 'grid');
    const value = loadPref('goals', 'planningView', 'month', {
      legacyKey: 'goals.planningView',
      isValid: (v) => v === 'month' || v === 'week',
    });
    expect(value).toBe('month');
  });
});
