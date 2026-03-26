import { writable } from 'svelte/store';

// ── Widget IDs ─────────────────────────────────────────────────────────────────
export type WidgetId =
  | 'plant-carousel'
  | 'stats-xp'
  | 'pomodoro'
  | 'recent-notes'
  | 'github-issues';

export interface WidgetMeta {
  id:    WidgetId;
  label: string;
  panel: 'left' | 'right'; // default panel
}

export const WIDGET_REGISTRY: Record<WidgetId, WidgetMeta> = {
  'plant-carousel': { id: 'plant-carousel', label: 'Módulo visual', panel: 'left'  },
  'stats-xp':       { id: 'stats-xp',       label: 'Stats & XP',   panel: 'left'  },
  'pomodoro':       { id: 'pomodoro',        label: 'Pomodoro',     panel: 'left'  },
  'recent-notes':   { id: 'recent-notes',    label: 'Notas',        panel: 'right' },
  'github-issues':  { id: 'github-issues',   label: 'GitHub',       panel: 'right' },
};

// ── Layout: two ordered columns ────────────────────────────────────────────────
export interface DashboardLayout {
  left:  WidgetId[];
  right: WidgetId[];
}

const DEFAULT: DashboardLayout = {
  left:  ['plant-carousel', 'stats-xp', 'pomodoro'],
  right: ['recent-notes', 'github-issues'],
};

const KEY = 'joidy-dashboard-layout-v2';

function load(): DashboardLayout {
  if (typeof localStorage === 'undefined') return DEFAULT;
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as DashboardLayout;
      if (Array.isArray(parsed.left) && Array.isArray(parsed.right)) return parsed;
    }
  } catch { /* */ }
  return DEFAULT;
}

function save(l: DashboardLayout) {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY, JSON.stringify(l));
}

function createLayoutStore() {
  const { subscribe, update, set } = writable<DashboardLayout>(load());

  return {
    subscribe,
    init() { set(load()); },

    // Move widget up/down within its panel
    move(panel: 'left' | 'right', fromIdx: number, toIdx: number) {
      update(l => {
        const col = [...l[panel]];
        const [item] = col.splice(fromIdx, 1);
        col.splice(toIdx, 0, item);
        const next = { ...l, [panel]: col };
        save(next);
        return next;
      });
    },

    // Move widget between panels
    switchPanel(id: WidgetId, from: 'left' | 'right') {
      const to = from === 'left' ? 'right' : 'left';
      update(l => {
        const src  = l[from].filter(w => w !== id);
        const dest = [...l[to], id];
        const next = { ...l, [from]: src, [to]: dest };
        save(next);
        return next;
      });
    },

    reset() { save(DEFAULT); set(DEFAULT); },
  };
}

export const dashboardLayout = createLayoutStore();
export const editMode        = writable(false);
