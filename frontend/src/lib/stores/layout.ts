import { writable } from 'svelte/store';

// ── Widget IDs ─────────────────────────────────────────────────────────────────
export type WidgetId =
  | 'plant-carousel'
  | 'stats-xp'
  | 'time-widget'
  | 'weather-widget'
  | 'pomodoro'
  | 'quick-capture'
  | 'mood-tracker'
  | 'recent-notes'
  | 'github-issues'
  | 'spotify-now-playing';

export interface WidgetMeta {
  id:    WidgetId;
  label: string;
  panel: 'left' | 'right'; // default panel
}

export const WIDGET_REGISTRY: Record<WidgetId, WidgetMeta> = {
  'plant-carousel':    { id: 'plant-carousel',    label: 'Módulo visual',          panel: 'left'  },
  'stats-xp':          { id: 'stats-xp',          label: 'Estadísticas y XP',      panel: 'left'  },
  'time-widget':       { id: 'time-widget',       label: 'Reloj',                  panel: 'left'  },
  'weather-widget': { id: 'weather-widget', label: 'Clima',         panel: 'left'  },
  'pomodoro':       { id: 'pomodoro',        label: 'Pomodoro',     panel: 'left'  },
  'quick-capture':  { id: 'quick-capture',   label: 'Captura rápida', panel: 'left' },
  'mood-tracker':   { id: 'mood-tracker',    label: 'Mood',         panel: 'left'  },
  'recent-notes':   { id: 'recent-notes',    label: 'Notas',        panel: 'right' },
  'github-issues':  { id: 'github-issues',   label: 'GitHub',       panel: 'right' },
  'spotify-now-playing': { id: 'spotify-now-playing', label: 'Spotify', panel: 'right' },
};

// ── Layout: two ordered columns (static, no reordering) ───────────────────────
export interface DashboardLayout {
  left:  WidgetId[];
  right: WidgetId[];
}

const DEFAULT: DashboardLayout = {
  left:  ['plant-carousel', 'stats-xp', 'time-widget', 'pomodoro'],
  right: ['github-issues', 'spotify-now-playing'],
};

export const dashboardLayout = writable<DashboardLayout>(DEFAULT);
