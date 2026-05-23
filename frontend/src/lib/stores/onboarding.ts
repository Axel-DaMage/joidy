import { writable } from 'svelte/store';

const ONBOARDING_KEY = 'joidy-onboarding-complete';

export interface OnboardingStep {
  id: string;
  title: string;
  content: string;
}

export const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    id: 'welcome',
    title: 'Bienvenido a Joidy',
    content: 'Tu sistema personal de gestión del conocimiento con gamificación. Aquí podrás tomar notas, establecer metas y seguir tu progreso.',
  },
  {
    id: 'notes',
    title: 'Notas',
    content: 'Crea y organiza tus notas. Cada nota puede tener etiquetas, iconos y colores personalizados. Las notas se sincronizan con tu bóveda de Obsidian.',
  },
  {
    id: 'goals',
    title: 'Metas',
    content: 'Establece metas personales con fechas objetivo. Completa metas para ganar XP y hacer crecer tu planta.',
  },
  {
    id: 'streaks',
    title: 'Rachas',
    content: 'Mantén una racha diaria de actividad. Cada día que interactúas con la app ganas XP y hace tu planta crecer.',
  },
];

function createOnboardingStore() {
  const { subscribe, set, update } = writable({
    completed: false,
    currentStep: 0,
    seen: false,
  });

  return {
    subscribe,
    init() {
      if (typeof localStorage !== 'undefined') {
        const completed = localStorage.getItem(ONBOARDING_KEY) === 'true';
        set({ completed, currentStep: 0, seen: !completed });
      }
    },
    nextStep() {
      update(state => {
        const next = state.currentStep + 1;
        if (next >= ONBOARDING_STEPS.length) {
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem(ONBOARDING_KEY, 'true');
          }
          return { completed: true, currentStep: 0, seen: false };
        }
        return { ...state, currentStep: next };
      });
    },
    prevStep() {
      update(state => ({
        ...state,
        currentStep: Math.max(0, state.currentStep - 1),
      }));
    },
    skip() {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(ONBOARDING_KEY, 'true');
      }
      set({ completed: true, currentStep: 0, seen: false });
    },
    close() {
      update(state => ({ ...state, seen: false }));
    },
  };
}

export const onboarding = createOnboardingStore();