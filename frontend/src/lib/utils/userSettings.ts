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