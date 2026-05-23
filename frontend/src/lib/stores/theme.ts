import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export interface Theme {
  id: string;
  name: string;
  colors: {
    background: string;
    surface: string;
    elevated: string;
    border: string;
    text: string;
    accent: string;
    success: string;
    error: string;
    warning: string;
  };
}

export const PRESET_THEMES: Theme[] = [
  {
    id: 'dark-default',
    name: 'Oscuro',
    colors: {
      background: '#0f0f0f',
      surface: '#1a1a1a',
      elevated: '#252525',
      border: '#333333',
      text: '#e0e0e0',
      accent: '#6366f1',
      success: '#22c55e',
      error: '#ef4444',
      warning: '#f59e0b',
    },
  },
  {
    id: 'light-default',
    name: 'Claro',
    colors: {
      background: '#f5f5f5',
      surface: '#ffffff',
      elevated: '#ffffff',
      border: '#e5e5e5',
      text: '#1a1a1a',
      accent: '#6366f1',
      success: '#16a34a',
      error: '#dc2626',
      warning: '#d97706',
    },
  },
  {
    id: 'ocean',
    name: 'Océano',
    colors: {
      background: '#0a192f',
      surface: '#112240',
      elevated: '#1d3557',
      border: '#233554',
      text: '#ccd6f6',
      accent: '#64ffda',
      success: '#4ade80',
      error: '#f87171',
      warning: '#fbbf24',
    },
  },
  {
    id: 'forest',
    name: 'Bosque',
    colors: {
      background: '#1a1c16',
      surface: '#242920',
      elevated: '#2f362b',
      border: '#3d4638',
      text: '#d4d8c8',
      accent: '#a3c585',
      success: '#86efac',
      error: '#fca5a5',
      warning: '#fcd34d',
    },
  },
  {
    id: 'sunset',
    name: 'Atardecer',
    colors: {
      background: '#1f1515',
      surface: '#2a1d1d',
      elevated: '#3a2626',
      border: '#4a3232',
      text: '#f0d8d8',
      accent: '#f472b6',
      success: '#fb7185',
      error: '#f87171',
      warning: '#fbbf24',
    },
  },
];

const THEME_KEY = 'joidy-theme';

function loadTheme(): Theme {
  if (!browser) return PRESET_THEMES[0];
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved) {
      const theme = JSON.parse(saved) as Theme;
      if (PRESET_THEMES.find(t => t.id === theme.id)) return theme;
    }
  } catch {}
  return PRESET_THEMES[0];
}

function createThemeStore() {
  const initialTheme = loadTheme();
  if (browser) applyTheme(initialTheme);
  const { subscribe, set, update } = writable<Theme>(initialTheme);

  return {
    subscribe,
    setTheme(theme: Theme) {
      if (!browser) return;
      localStorage.setItem(THEME_KEY, JSON.stringify(theme));
      applyTheme(theme);
      set(theme);
    },
    reset() {
      if (!browser) return;
      localStorage.removeItem(THEME_KEY);
      applyTheme(PRESET_THEMES[0]);
      set(PRESET_THEMES[0]);
    },
  };
}

export function applyTheme(theme: Theme) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;

  root.style.setProperty('--bg', theme.colors.background);
  root.style.setProperty('--surface', theme.colors.surface);
  root.style.setProperty('--elevated', theme.colors.elevated);
  root.style.setProperty('--border', theme.colors.border);
  root.style.setProperty('--text-primary', theme.colors.text);
  root.style.setProperty('--accent', theme.colors.accent);
  root.style.setProperty('--success', theme.colors.success);
  root.style.setProperty('--error', theme.colors.error);
  root.style.setProperty('--warning', theme.colors.warning);
}

export const theme = createThemeStore();