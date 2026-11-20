import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

// Mock $app/env so `browser` is true (jsdom provides storage).
vi.mock('$app/env', () => ({ browser: true, dev: false }));

// IndexedDB is not available in jsdom — spy on the wrapper instead.
const { clearUserDataMock } = vi.hoisted(() => ({
  clearUserDataMock: vi.fn(),
}));
vi.mock('$lib/utils/indexedDB', () => ({
  clearUserData: clearUserDataMock,
}));

import { session, SESSION_RESET_EVENT } from './session';

const USER_SESSION = {
  id: 'u1',
  username: 'alice',
  token: 'jwt-abc',
  preferences: { theme: 'dark' as const, timezone: 'UTC', language: 'en' },
  createdAt: '2025-01-01T00:00:00Z',
};

// Keys that MUST be wiped by logout (#1325).
const PURGED_KEYS = [
  'joidy_session',
  'joidy-draft-42',
  'joidy-draft-new',
  'joidy-goal-draft-7',
  'joidy_route_cache',
  'joidy_github_cache_v2',
  'joidy-user-settings-v1',
  'joidy-achievements',
  'joidy-last-ping',
  'joidy-weather-location',
  'joidy-weather-cache',
  'joidy-graph-color-groups',
  'joidy-folder-meta',
  'goals.currentTab',
  'goals.selectedPlanningDate',
  'goals.historyView',
] as const;

// Device-level prefs that must survive logout.
const SURVIVING_KEYS = [
  'joidy-theme-mode',
  'joidy-dev-mode',
  'joidy-icon-pack',
  'joidy:locale',
  'joidy-timezone',
  'joidy-onboarding-complete',
] as const;

describe('session.logout() — user data purge (#1325)', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    clearUserDataMock.mockReset().mockResolvedValue(undefined);
  });

  it('removes every user-scoped localStorage key, keeps device prefs', () => {
    session.login(USER_SESSION);
    for (const key of PURGED_KEYS) {
      if (key !== 'joidy_session') localStorage.setItem(key, 'payload');
    }
    for (const key of SURVIVING_KEYS) localStorage.setItem(key, 'pref');
    sessionStorage.setItem('joidy_chat_messages', '[]');
    sessionStorage.setItem('joidy_page_snapshots', '{}');

    let resetFired = false;
    window.addEventListener(SESSION_RESET_EVENT, () => (resetFired = true), { once: true });

    session.logout();

    for (const key of PURGED_KEYS) {
      expect(localStorage.getItem(key), `${key} should be purged`).toBeNull();
    }
    for (const key of SURVIVING_KEYS) {
      expect(localStorage.getItem(key), `${key} should survive`).toBe('pref');
    }
    expect(sessionStorage.length).toBe(0);
    expect(get(session)).toBeNull();
    expect(resetFired).toBe(true);
    expect(clearUserDataMock).toHaveBeenCalledTimes(1);
  });

  it('does not remove device prefs when nothing was stored', () => {
    localStorage.setItem('joidy-theme-mode', 'light');
    session.logout();
    expect(localStorage.getItem('joidy-theme-mode')).toBe('light');
    expect(get(session)).toBeNull();
  });
});
