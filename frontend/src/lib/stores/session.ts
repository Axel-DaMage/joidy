import { writable } from 'svelte/store';
import { browser } from '$app/env';
import { clearUserData } from '$lib/utils/indexedDB';

export interface UserSession {
  id: string;
  username: string;
  email?: string;
  avatar?: string;
  token?: string;
  preferences: {
    theme: 'dark' | 'light';
    timezone: string;
    language: string;
  };
  createdAt: string;
}

const SESSION_KEY = 'joidy_session';

function loadSession(): UserSession | null {
  if (!browser) return null;
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveSession(session: UserSession | null) {
  if (!browser) return;
  if (session) {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } else {
    localStorage.removeItem(SESSION_KEY);
  }
}

function createSessionStore() {
  const { subscribe, set, update } = writable<UserSession | null>(loadSession());

  return {
    subscribe,
    login(session: UserSession) {
      saveSession(session);
      set(session);
    },
    logout() {
      saveSession(null);
      set(null);
      resetSession();
      clearServiceWorkerCaches();
    },
    setToken(token: string) {
      update((s) => {
        if (!s) return null;
        const updated = { ...s, token };
        saveSession(updated);
        return updated;
      });
    },
    updatePreferences(prefs: Partial<UserSession['preferences']>) {
      update((s) => {
        if (!s) return null;
        const updated = { ...s, preferences: { ...s.preferences, ...prefs } };
        saveSession(updated);
        return updated;
      });
    },
    updateProfile(data: Partial<Pick<UserSession, 'username' | 'email' | 'avatar'>>) {
      update((s) => {
        if (!s) return null;
        const updated = { ...s, ...data };
        saveSession(updated);
        return updated;
      });
    },
  };
}

export const session = createSessionStore();

/**
 * Wipes every `joidy-*` CacheStorage cache on logout/session reset so
 * runtime-cached responses can never leak to the next user of the same
 * browser profile (#1310). Precached build assets simply re-fetch on demand
 * via the service worker's cacheFirst handler.
 */
function clearServiceWorkerCaches(): void {
  if (!browser || !('caches' in window)) return;
  caches
    .keys()
    .then((keys) =>
      Promise.all(keys.filter((key) => key.startsWith('joidy-')).map((key) => caches.delete(key)))
    )
    .catch(() => {
      /* best-effort cleanup */
    });
}

export const isAuthenticated = {
  subscribe: (run: (value: boolean) => void) => {
    return session.subscribe((s) => run(!!s));
  },
};

export function getToken(): string | null {
  if (!browser) return null;
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as UserSession;
    return s.token ?? null;
  } catch {
    return null;
  }
}

export function saveToken(token: string) {
  if (!browser) return;
  // Route through the store so $session.token stays in sync — the previous
  // implementation mutated localStorage only, leaving the in-memory session
  // stale while getToken() returned the new token (#1305).
  session.setToken(token);
}

/**
 * Custom event fired on logout/session reset so user-scoped stores can drop
 * their in-memory state without importing each other (avoids import cycles:
 * session ← api ← feature stores). Subscribe in browser contexts only (#1305).
 */
export const SESSION_RESET_EVENT = 'joidy:session-reset';

/** localStorage keys that hold user data rather than device-level prefs
 *  (theme, icon pack, dev mode etc. intentionally survive logout). */
const USER_DATA_KEYS = [
  'joidy-achievements',
  'joidy_route_cache',
  'joidy_github_cache_v2',
  'joidy-user-settings-v1',
  'joidy-last-ping',
  // Geolocation coords + cached weather payload (#1325).
  'joidy-weather-location',
  'joidy-weather-cache',
  // User-entered tag queries used to color graph groups (#1325).
  'joidy-graph-color-groups',
  // Vault folder paths → icon/color metadata (#1325).
  'joidy-folder-meta',
] as const;

const USER_DATA_PREFIXES = [
  'goals.',
  // Note/goal editor draft payloads — full note text (#1325).
  'joidy-draft-',
  'joidy-goal-draft-',
] as const;

/**
 * Wipes user-scoped persisted state on logout so the next session on the
 * same browser profile cannot observe the previous user's data (#1305).
 * SessionStorage is cleared wholesale — every key written there is
 * user-scoped (chat messages, notes/data caches). The IndexedDB `joidy`
 * database (notes cache + offline outbox) is dropped via clearUserData()
 * (#1325).
 */
function resetSession(): void {
  if (!browser) return;
  try {
    for (const key of USER_DATA_KEYS) localStorage.removeItem(key);
    const prefixed: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && USER_DATA_PREFIXES.some((p) => key.startsWith(p))) prefixed.push(key);
    }
    for (const key of prefixed) localStorage.removeItem(key);
  } catch {
    /* best-effort cleanup */
  }
  try {
    sessionStorage.clear();
  } catch {
    /* best-effort cleanup */
  }
  // Fire-and-forget — logout must not block on cache cleanup.
  void clearUserData();
  window.dispatchEvent(new Event(SESSION_RESET_EVENT));
}
