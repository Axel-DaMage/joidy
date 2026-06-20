import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';

export interface AnalyticsEvent {
  name: string;
  data?: Record<string, any>;
  timestamp: number;
}

interface AnalyticsState {
  events: AnalyticsEvent[];
  pageViews: number;
  sessionStart: number;
  userId: string | null;
}

const MAX_EVENTS = 100;
const ANALYTICS_KEY = 'joidy_analytics';

function createAnalyticsStore() {
  const loadState = (): AnalyticsState => {
    if (!browser) return { events: [], pageViews: 0, sessionStart: Date.now(), userId: null };
    try {
      const saved = localStorage.getItem(ANALYTICS_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Date.now() - parsed.sessionStart < 30 * 60 * 1000) {
          return parsed;
        }
      }
    } catch {}
    return {
      events: [],
      pageViews: 0,
      sessionStart: Date.now(),
      userId: generateUserId(),
    };
  };

  const { subscribe, update } = writable<AnalyticsState>(loadState());

  function save(state: AnalyticsState) {
    if (!browser) return;
    try {
      localStorage.setItem(ANALYTICS_KEY, JSON.stringify(state));
    } catch {}
  }

  return {
    subscribe,

    trackEvent(name: string, data?: Record<string, any>) {
      update(state => {
        const event = { name, data, timestamp: Date.now() };
        const events = [...state.events, event].slice(-MAX_EVENTS);
        const newState = { ...state, events };
        save(newState);
        return newState;
      });
    },

    trackPageView(path: string) {
      update(state => {
        const event = { name: 'page_view', data: { path }, timestamp: Date.now() };
        const events = [...state.events, event].slice(-MAX_EVENTS);
        const newState = { ...state, events, pageViews: state.pageViews + 1 };
        save(newState);
        return newState;
      });
    },

    getEventCount(name?: string): number {
      const state = get({ subscribe });
      if (!name) return state.events.length;
      return state.events.filter(e => e.name === name).length;
    },

    getSessionDuration(): number {
      const state = get({ subscribe });
      return Date.now() - state.sessionStart;
    },

    reset() {
      const fresh: AnalyticsState = {
        events: [],
        pageViews: 0,
        sessionStart: Date.now(),
        userId: generateUserId(),
      };
      update(() => fresh);
      save(fresh);
    },
  };
}

function generateUserId(): string {
  return 'user_' + Math.random().toString(36).slice(2, 11) + Date.now().toString(36);
}

export const analytics = createAnalyticsStore();