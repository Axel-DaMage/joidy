export interface UserSettings {
  dashboard?: {
    moduleId?: string;
    panelWidth?: number;
  };
  pomodoro?: {
    workMins?: number;
    breakMins?: number;
  };
  notesUi?: {
    panelWidth?: number;
    sortMode?: string;
    viewMode?: 'tree' | 'list';
    allCollapsed?: boolean;
    collapsedPaths?: string[];
    search?: string;
    selectedNoteId?: number | null;
    treeScrollTop?: number;
    listScrollTop?: number;
  };
  streaksUi?: {
    panelWidth?: number;
  };
}

const KEY = 'joidy-user-settings-v1';

const CACHE_KEYS = {
  notes: 'joidy_data_notes',
  streaks: 'joidy_data_streaks',
  goals: 'joidy_data_goals',
  stats: 'joidy_data_stats',
  tags: 'joidy_data_tags',
} as const;

export function getCachedData<T>(key: keyof typeof CACHE_KEYS): T | null {
  if (typeof sessionStorage === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(CACHE_KEYS[key]);
    if (!raw) return null;
    const cached = JSON.parse(raw) as { data: T; ts: number };
    if (Date.now() - cached.ts > 300000) return null;
    return cached.data;
  } catch {
    return null;
  }
}

export function setCachedData<T>(key: keyof typeof CACHE_KEYS, data: T): void {
  if (typeof sessionStorage === 'undefined') return;
  try {
    sessionStorage.setItem(CACHE_KEYS[key], JSON.stringify({ data, ts: Date.now() }));
  } catch {}
}

export function loadUserSettings(): UserSettings {
  if (typeof localStorage === 'undefined') return {};
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as UserSettings;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

export function patchUserSettings(patch: Partial<UserSettings>): void {
  if (typeof localStorage === 'undefined') return;
  const current = loadUserSettings();
  const next: UserSettings = {
    ...current,
    ...patch,
    dashboard: { ...current.dashboard, ...patch.dashboard },
    pomodoro: { ...current.pomodoro, ...patch.pomodoro },
    notesUi: { ...current.notesUi, ...patch.notesUi },
    streaksUi: { ...current.streaksUi, ...patch.streaksUi },
  };
  localStorage.setItem(KEY, JSON.stringify(next));
}