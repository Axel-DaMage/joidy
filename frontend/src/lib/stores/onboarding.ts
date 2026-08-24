import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { api } from '$lib/api';

const ONBOARDING_KEY = 'joidy-onboarding-complete';

export interface OnboardingStep {
  id: string;
  /** i18n key prefix, e.g. "onboarding.welcome" — title/content resolved via $t(). */
  titleKey: string;
  contentKey: string;
  /** CSS selector for the element to spotlight. null = centered (no target). */
  target: string | null;
}

export const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    id: 'welcome',
    titleKey: 'onboarding.welcome.title',
    contentKey: 'onboarding.welcome.content',
    target: null,
  },
  {
    id: 'notes',
    titleKey: 'onboarding.notes.title',
    contentKey: 'onboarding.notes.content',
    target: 'a.nav-item[href="/notes"]',
  },
  {
    id: 'tags',
    titleKey: 'onboarding.tags.title',
    contentKey: 'onboarding.tags.content',
    target: 'a.nav-item[href="/graph"]',
  },
  {
    id: 'goals',
    titleKey: 'onboarding.goals.title',
    contentKey: 'onboarding.goals.content',
    target: 'a.nav-item[href="/goals"]',
  },
  {
    id: 'streaks',
    titleKey: 'onboarding.streaks.title',
    contentKey: 'onboarding.streaks.content',
    target: 'a.nav-item[href="/streaks"]',
  },
  {
    id: 'obsidian',
    titleKey: 'onboarding.obsidian.title',
    contentKey: 'onboarding.obsidian.content',
    target: null,
  },
];

interface OnboardingState {
  completed: boolean;
  currentStep: number;
  active: boolean;
}

function createOnboardingStore() {
  const { subscribe, set, update } = writable<OnboardingState>({
    completed: false,
    currentStep: 0,
    active: false,
  });

  const markCompleted = () => {
    if (browser) {
      localStorage.setItem(ONBOARDING_KEY, 'true');
    }
  };

  return {
    subscribe,
    init() {
      if (browser) {
        const completed = localStorage.getItem(ONBOARDING_KEY) === 'true';
        set({ completed, currentStep: 0, active: false });
      }
    },
    /** Whether the user has finished the onboarding tour (persisted). */
    hasCompletedOnboarding: (() => {
      const store = writable<boolean>(false);
      if (browser) {
        store.set(localStorage.getItem(ONBOARDING_KEY) === 'true');
      }
      return store;
    })(),
    /** Current step index (0-based). */
    currentStep: writable<number>(0),
    /**
     * Returns true on a first visit: no localStorage flag AND no notes/goals
     * exist yet. Resolves asynchronously; returns false when not in browser.
     */
    async shouldShowOnboarding(): Promise<boolean> {
      if (!browser) return false;
      if (localStorage.getItem(ONBOARDING_KEY) === 'true') return false;

      try {
        const [notes, goals] = await Promise.all([
          api.notes.list().catch(() => []),
          api.goals.list().catch(() => []),
        ]);
        return notes.length === 0 && goals.length === 0;
      } catch {
        // If we can't reach the API, fall back to the localStorage flag only.
        return false;
      }
    },
    startTour() {
      update((state) => ({ ...state, currentStep: 0, active: true }));
      if (browser) localStorage.removeItem(ONBOARDING_KEY);
    },
    nextStep() {
      update((state) => {
        const next = state.currentStep + 1;
        if (next >= ONBOARDING_STEPS.length) {
          markCompleted();
          return { completed: true, currentStep: 0, active: false };
        }
        return { ...state, currentStep: next };
      });
    },
    prevStep() {
      update((state) => ({ ...state, currentStep: Math.max(0, state.currentStep - 1) }));
    },
    skipTour() {
      markCompleted();
      set({ completed: true, currentStep: 0, active: false });
    },
    completeTour() {
      markCompleted();
      set({ completed: true, currentStep: 0, active: false });
    },
    /** Legacy alias kept for backwards compatibility. */
    skip() {
      markCompleted();
      set({ completed: true, currentStep: 0, active: false });
    },
    close() {
      update((state) => ({ ...state, active: false }));
    },
  };
}

export const onboarding = createOnboardingStore();
