import { writable } from 'svelte/store';
import { browser } from '$app/env';

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
      clearServiceWorkerCaches();
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
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return;
    const s = JSON.parse(raw) as UserSession;
    s.token = token;
    localStorage.setItem(SESSION_KEY, JSON.stringify(s));
  } catch {
    // ignore
  }
}
