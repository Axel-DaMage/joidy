import { writable } from 'svelte/store';

// ── Widget IDs ─────────────────────────────────────────────────────────────────
export type WidgetId =
  | 'plant-carousel'
  | 'stats-xp'
  | 'activity-progress'
  | 'time-widget'
  | 'weather-widget'
  | 'pomodoro'
  | 'recent-notes'
  | 'github-issues';

export interface WidgetMeta {
  id:    WidgetId;
  label: string;
  panel: 'left' | 'right'; // default panel
}

export const WIDGET_REGISTRY: Record<WidgetId, WidgetMeta> = {
  'plant-carousel':    { id: 'plant-carousel',    label: 'Módulo visual',          panel: 'left'  },
  'stats-xp':          { id: 'stats-xp',          label: 'Estadísticas y XP',      panel: 'left'  },
  'activity-progress': { id: 'activity-progress', label: 'Actividad semanal',      panel: 'left'  },
  'time-widget':       { id: 'time-widget',       label: 'Reloj',                  panel: 'left'  },
  'weather-widget': { id: 'weather-widget', label: 'Clima',         panel: 'left'  },
  'pomodoro':       { id: 'pomodoro',        label: 'Pomodoro',     panel: 'left'  },
  'recent-notes':   { id: 'recent-notes',    label: 'Notas',        panel: 'right' },
  'github-issues':  { id: 'github-issues',   label: 'GitHub',       panel: 'right' },
};

// ── Layout: two ordered columns (static, no reordering) ───────────────────────
export interface DashboardLayout {
  left:  WidgetId[];
  right: WidgetId[];
}

const DEFAULT: DashboardLayout = {
  left:  ['plant-carousel', 'stats-xp', 'activity-progress', 'time-widget', 'pomodoro'],
  right: ['recent-notes', 'github-issues'],
};

export const dashboardLayout = writable<DashboardLayout>(DEFAULT);
