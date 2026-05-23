import { writable } from 'svelte/store';

export interface UserSession {
  id: string;
  username: string;
  email?: string;
  avatar?: string;
  preferences: {
    theme: 'dark' | 'light';
    timezone: string;
    language: string;
  };
  createdAt: string;
}

const SESSION_KEY = 'joidy_session';

function loadSession(): UserSession | null {
  if (typeof localStorage === 'undefined') return null;
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveSession(session: UserSession | null) {
  if (typeof localStorage === 'undefined') return;
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
    },
    updatePreferences(prefs: Partial<UserSession['preferences']>) {
      update(s => {
        if (!s) return null;
        const updated = { ...s, preferences: { ...s.preferences, ...prefs } };
        saveSession(updated);
        return updated;
      });
    },
    updateProfile(data: Partial<Pick<UserSession, 'username' | 'email' | 'avatar'>>) {
      update(s => {
        if (!s) return null;
        const updated = { ...s, ...data };
        saveSession(updated);
        return updated;
      });
    },
  };
}

export const session = createSessionStore();

export const isAuthenticated = {
  subscribe: (run: (value: boolean) => void) => {
    return session.subscribe(s => run(!!s));
  }
};