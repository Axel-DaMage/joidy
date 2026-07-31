import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { api } from '$lib/api';

const ONBOARDING_KEY = 'joidy-onboarding-complete';

export interface OnboardingStep {
  id: string;
  title: string;
  content: string;
  /** CSS selector for the element to spotlight. null = centered (no target). */
  target: string | null;
}

export const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    id: 'welcome',
    title: 'Bienvenida a Joidy',
    content:
      'Tu sistema personal de gestión del conocimiento con gamificación. Aquí tomarás notas, establecerás metas y harás crecer una planta mientras mantienes rachas diarias.',
    target: null,
  },
  {
    id: 'notes',
    title: 'Crea tu primera nota',
    content:
      'En la página de Notas puedes crear y organizar tu conocimiento. Cada nota admite etiquetas, iconos y colores, y se sincroniza con tu bóveda de Obsidian.',
    target: 'a.nav-item[href="/notes"]',
  },
  {
    id: 'tags',
    title: 'Tags y grafo',
    content:
      'Etiqueta tus notas para conectarlas. El Grafo visualiza cómo se relacionan tus notas a través de los tags, revelando patrones y temas en tu conocimiento.',
    target: 'a.nav-item[href="/graph"]',
  },
  {
    id: 'goals',
    title: 'Tu primera meta',
    content:
      'Establece metas con temporalidades (diaria, semanal, mensual o anual). Completar metas te da XP y alimenta tu progreso. Empieza con algo pequeño y alcanzable.',
    target: 'a.nav-item[href="/goals"]',
  },
  {
    id: 'streaks',
    title: 'Rachas y planta',
    content:
      'Mantén una racha diaria de actividad. Cada día que interactúas con Joidy ganas XP y tu planta crece: de semilla a árbol. ¡No rompas la cadena!',
    target: 'a.nav-item[href="/streaks"]',
  },
  {
    id: 'obsidian',
    title: 'Conecta Obsidian (opcional)',
    content:
      'Joidy se sincroniza con tu bóveda de Obsidian para mantener tus notas en formato Markdown. Puedes configurarlo ahora desde Ajustes, o saltar este paso y hacerlo más tarde.',
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
      update(state => ({ ...state, currentStep: 0, active: true }));
      if (browser) localStorage.removeItem(ONBOARDING_KEY);
    },
    nextStep() {
      update(state => {
        const next = state.currentStep + 1;
        if (next >= ONBOARDING_STEPS.length) {
          markCompleted();
          return { completed: true, currentStep: 0, active: false };
        }
        return { ...state, currentStep: next };
      });
    },
    prevStep() {
      update(state => ({ ...state, currentStep: Math.max(0, state.currentStep - 1) }));
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
      update(state => ({ ...state, active: false }));
    },
  };
}

export const onboarding = createOnboardingStore();
