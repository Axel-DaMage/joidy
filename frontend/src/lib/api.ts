// API base URL — browser uses VITE_API_URL (public), SSR uses INTERNAL_API_URL
// (Docker internal network). This prevents network failures when SvelteKit
// server-renders pages inside the container where localhost:PORT isn't mapped.
import { browser } from '$app/environment';
import { showNotification } from './stores/notifications';
import { session, getToken } from './stores/session';

const BASE = browser
  ? ((import.meta.env.VITE_API_URL as string) || 'http://localhost:8000')
  : (import.meta.env.VITE_INTERNAL_API_URL as string || import.meta.env.VITE_API_URL as string || 'http://localhost:8000');

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  try {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (body) headers['Content-Type'] = 'application/json';
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined
    });

    if (res.status === 401) {
      session.logout();
      showNotification('Sesión expirada. Por favor, vuelve a iniciar sesión.', 'error');
      throw new Error(`API ${method} ${path} → 401 Unauthorized`);
    }

    if (!res.ok) {
      const err = await res.text().catch(() => res.statusText);
      const errorMsg = err || res.statusText || 'Error desconocido';
      showNotification(`Error del servidor (${res.status}): ${errorMsg}`, 'error');
      throw new Error(`API ${method} ${path} → ${res.status}: ${err}`);
    }

    if (res.status === 204) return undefined as T;
    return res.json();
  } catch (error: any) {
    if (error.name === 'TypeError' || error.message.includes('Failed to fetch') || error.message.includes('fetch failed')) {
      showNotification('Error de red. No se pudo conectar con el servidor.', 'error');
    }
    throw error;
  }
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Note {
  id: number;
  title: string;
  content: string;
  source: string;
  source_path: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface Tag {
  id: number;
  name: string;
  parent_id: number | null;
  note_count: number;
}

export interface GamificationStats {
  total_xp: number;
  current_streak: number;
  longest_streak: number;
  plant_stage: number;
  plant_stage_name: string;
  next_stage_xp: number | null;
  xp_to_next_stage: number | null;
  last_activity_date: string | null;
}

export interface GamificationResult {
  xp_awarded: number;
  total_xp: number;
  current_streak: number;
  longest_streak?: number;
  plant_stage: number;
  plant_stage_name: string;
  plant_stage_changed: boolean;
  streak_changed: boolean;
  milestone_reached: number | null;
  message: string;
  next_stage_xp?: number | null;
  xp_to_next_stage?: number | null;
  last_activity_date?: string | null;
}

export interface Skill {
  id: number;
  tag_id: number;
  tag_name: string;
  level: string;
  note_count: number;
  first_unlocked_at: string | null;
}

export interface SkillNode { id: number; name: string; level: string; note_count: number; xp: number; }
export interface SkillEdge { source: number; target: number; }
export interface SkillTree { nodes: SkillNode[]; edges: SkillEdge[]; }

export interface Goal {
  id: number;
  title: string;
  description: string;
  source_path: string | null;
  temporality: 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'ANNUAL';
  measurement_type: 'COUNT' | 'BOOLEAN' | 'PERCENT';
  target_value: number;
  current_value: number;
  state: 'ACTIVE' | 'COMPLETED' | 'FAILED' | 'PAUSED' | 'CANCELLED';
  fail_config: 'STATIC' | 'ROLLOVER' | 'SNOWBALL';
  fail_emoji: string;
  color: string;
  theme: string;
  note_id: number | null;
  tag_id: number | null;
  parent_id: number | null;
  max_assignment_days: number | null;
  progress_pct: number;
  pending_removal: boolean;
  is_completed: boolean;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GraphNode {
  id: number | string;
  type: 'tag' | 'note' | 'unresolved';
  name?: string;
  title?: string;
  note_count?: number;
  parent_id?: number | string | null;
  path?: string | null;
  tags?: string[];
  group: string;
}
export interface GraphEdge { source: number | string; target: number | string; type: 'hierarchy' | 'cooccurrence' | 'linked' | 'tagged'; weight?: number; }
export interface GraphData { nodes: GraphNode[]; edges: GraphEdge[]; }

export interface AISuggestion { tag: string; confidence: number; is_new: boolean; }

export interface StreakDay {
  date: string;
  checked: boolean;
  note?: string;
  mood?: number;
}

export interface PersonalStreak {
  id: number;
  name: string;
  emoji: string;
  icon: string;
  description: string;
  color: string;
  theme: string;
  category: string;
  start_date: string | null;
  target_date: string | null;
  offset: number;
  frequency: string;
  frequency_days: number;
  is_archived: boolean;
  current_streak: number;
  longest_streak: number;
  best_streak: number;
  total_checkins: number;
  freeze_count: number;
  freeze_used: number;
  days_remaining: number | null;
  completion_pct: number | null;
  today_checked: boolean;
  history: StreakDay[];
  created_at: string;
}

export interface StreakStats {
  total_active: number;
  total_archived: number;
  longest_ever: number;
  longest_name: string;
  total_checkins: number;
  checkin_rate: number;
  days_tracked: number;
}

// ── Notes ─────────────────────────────────────────────────────────────────────

export const api = {
  notes: {
    list:   (tag?: string, limit = 1000) => req<Note[]>('GET', `/notes/?limit=${limit}${tag ? `&tag=${encodeURIComponent(tag)}` : ''}`),
    get:    (id: number)   => req<Note>('GET', `/notes/${id}`),
    create: (data: { title: string; content: string; tags: string[]; source_path?: string | null; source?: string }) =>
      req<Note & { gamification: GamificationResult }>('POST', '/notes/', data),
    update: (id: number, data: Partial<{ title: string; content: string; tags: string[] }>) =>
      req<Note & { gamification: GamificationResult }>('PUT', `/notes/${id}`, data),
    delete: (id: number)   => req<void>('DELETE', `/notes/${id}`),
    acceptTag: (noteId: number, tag: string) =>
      req<{ tag: string; gamification: GamificationResult }>('POST', `/notes/${noteId}/accept-tag?tag_name=${encodeURIComponent(tag)}`),
    backlinks: (id: number) => req<Note[]>('GET', `/notes/${id}/backlinks`),
  },

  tags: {
    list:  ()           => req<Tag[]>('GET', '/tags/'),
    graph: ()           => req<GraphData>('GET', '/tags/graph'),
    create: (name: string, parent_id?: number) => req<Tag>('POST', '/tags/', { name, parent_id }),
  },

  gamification: {
    stats:   ()          => req<GamificationStats>('GET', '/gamification/stats'),
    ping:    ()          => req<GamificationResult>('POST', '/gamification/ping'),
    history: (days = 30) => req<{ date: string; xp: number }[]>('GET', `/gamification/streak-history?days=${days}`),
    events:  (limit = 20)=> req<{ type: string; xp: number; at: string }[]>('GET', `/gamification/recent-events?limit=${limit}`),
  },

  skills: {
    list: () => req<Skill[]>('GET', '/skills/'),
    tree: () => req<SkillTree>('GET', '/skills/tree'),
    sync: () => req<{ synced: number }>('POST', '/skills/sync'),
  },

  goals: {
    list:     ()                    => req<Goal[]>('GET', '/goals/'),
    get:      (id: number)        => req<Goal>('GET', `/goals/${id}`),
    create:   (data: { title: string; description?: string; temporality?: string; measurement_type?: string; target_value?: number; fail_config?: string; fail_emoji?: string; color?: string; theme?: string; tag_id?: number | null; note_id?: number | null; parent_id?: number | null; max_assignment_days?: number | null }) =>
      req<Goal>('POST', '/goals/', data),
    update:   (id: number, data: Partial<Goal>) => req<Goal>('PUT', `/goals/${id}`, data),
    complete: (id: number) =>
      req<{ goal: Goal; gamification: GamificationResult }>('POST', `/goals/${id}/complete`),
    delete:   (id: number) => req<void>('DELETE', `/goals/${id}`),
    streak:   () => req<{ current_streak: number; best_streak: number }>('GET', '/goals/streak'),
    resolveRemoval: (id: number, action: 'delete' | 'manual' | 'cancel') =>
      req<Goal | { status: string }>('POST', `/goals/${id}/resolve-removal`, { action }),
    getContent:  (id: number) => req<{ title: string; content: string; temporality?: string; measurement_type?: string; state?: string; fail_config?: string; fail_emoji?: string; color?: string }>('GET', `/goals/${id}/content`),
    saveContent: (id: number, data: { title: string; content: string; temporality?: string; measurement_type?: string; target_value?: number; state?: string; fail_config?: string; fail_emoji?: string; color?: string; theme?: string; note_id?: number | null; tag_id?: number | null; parent_id?: number | null; max_assignment_days?: number | null; description?: string }) =>
      req<Goal>('POST', `/goals/${id}/content`, data),
  },

  planning: {
    getAssignments: (date: string) => req<{ date: string; goal_ids: number[] }>('GET', `/planning/assignments?date=${encodeURIComponent(date)}`),
    setAssignments: (date: string, goal_ids: number[]) => req<{ date: string; goal_ids: number[] }>('POST', '/planning/assignments', { date, goal_ids }),
  },

  personalStreaks: {
    list: (opts?: { include_archived?: boolean; category?: string }) => {
      const params = new URLSearchParams();
      if (opts?.include_archived) params.set('include_archived', 'true');
      if (opts?.category) params.set('category', opts.category);
      const qs = params.toString();
      return req<PersonalStreak[]>('GET', `/personal-streaks/${qs ? '?' + qs : ''}`);
    },
    create: (data: {
      name: string; emoji?: string; icon?: string; description?: string;
      color?: string; theme?: string; category?: string;
      start_date?: string | null; target_date?: string | null;
      offset?: number; frequency?: string; frequency_days?: number;
      freeze_count?: number;
    }) => req<PersonalStreak>('POST', '/personal-streaks/', data),
    update: (id: number, data: {
      name?: string; emoji?: string; icon?: string; description?: string;
      color?: string; theme?: string; category?: string;
      start_date?: string | null; target_date?: string | null;
      offset?: number; frequency?: string; frequency_days?: number;
      is_archived?: boolean; freeze_count?: number;
    }) => req<PersonalStreak>('PUT', `/personal-streaks/${id}`, data),
    delete:   (id: number)        => req<void>('DELETE', `/personal-streaks/${id}`),
    checkin:  (id: number, data?: { note?: string; mood?: number; check_date?: string }) =>
      req<PersonalStreak>('POST', `/personal-streaks/${id}/checkin`, data || {}),
    undo:     (id: number)        => req<PersonalStreak>('DELETE', `/personal-streaks/${id}/checkin`),
    freeze:   (id: number)        => req<PersonalStreak>('POST', `/personal-streaks/${id}/freeze`),
    stats:    ()                  => req<StreakStats>('GET', '/personal-streaks/stats'),
    categories: ()                => req<string[]>('GET', '/personal-streaks/categories'),
    history:  (id: number, days = 90) => req<{ date: string; note: string; mood: number | null; created_at: string }[]>('GET', `/personal-streaks/${id}/history?days=${days}`),
  },

  ai: {
    classify: (noteId: number, content: string, existingTags: string[]) =>
      req<{ note_id: number; status: string; suggestions: AISuggestion[] }>('POST', '/ai/classify', { note_id: noteId, content, existing_tags: existingTags }),
    usage: () => req<{ ai_enabled: boolean; estimated_cost_usd: number }>('GET', '/ai/usage'),
  },

github: {
    status: () => req<{ connected: boolean; username: string | null }>('GET', '/integrations/github/status'),
    issues: (filter: string = 'all') => req<{ issues: { id: number; number: number; title: string; repo: string; url: string; state: string; updated_at: string; author?: string }[]; stats: { total: number; open: number; closed: number }; filter: string }>('GET', `/integrations/github/issues?filter=${filter}`),
    pulls: (filter: string = 'all') => req<{ pulls: { id: number; number: number; title: string; repo: string; url: string; state: string; draft: boolean; updated_at: string; author?: string }[]; stats: { total: number; open: number; closed: number; draft: number }; filter: string }>('GET', `/integrations/github/pulls?filter=${filter}`),
    repos: () => req<{ repos: { id: number; name: string; full_name: string; color: string }[] }>('GET', '/integrations/github/repos'),
  },

  config: {
    get: () => req<{
      gemini_api_key: string | null;
      obsidian_vault_path: string | null;
      daily_notes_folder: string | null;
      github_username: string | null;
      app_env: string | null;
      configured_keys: string[];
    }>('GET', '/config/'),
    update: (data: {
      gemini_api_key?: string;
      obsidian_vault_path?: string;
      daily_notes_folder?: string;
      github_token?: string;
      github_username?: string;
      github_client_id?: string;
      github_client_secret?: string;
      telegram_bot_token?: string;
      telegram_allowed_user_id?: string;
    }) => req<{ status: string; message: string }>('POST', '/config/', data),
    keys: () => req<{
      keys: { key: string; env_key: string; public: boolean; description: string }[];
    }>('GET', '/config/keys'),
    gamification: () => req<{
      xp_table: Record<string, number>;
      plant_stages: { stage: number; name: string; xp_required: number }[];
      streak_milestones: number[];
    }>('GET', '/config/gamification'),
  },
  stats: {
    system: () => req<{
      notes: number;
      tags: number;
      goals: number;
      skills: number;
      total_xp: number;
      current_streak: number;
      xp_events_week: number;
    }>('GET', '/stats/system'),
    activity: (days = 30) => req<{
      days: { date: string; notes_created: number; xp_events: number }[];
    }>('GET', `/stats/activity?days=${days}`),
  },
  export: {
    markdownUrl: () => `${BASE}/export/notes/markdown`,
    htmlUrl: () => `${BASE}/export/notes/html`,
    zipUrl: () => `${BASE}/export/notes/zip`
  },
};
