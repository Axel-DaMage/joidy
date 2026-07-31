// API base URL — browser uses VITE_API_URL (public), SSR uses INTERNAL_API_URL
// (Docker internal network). This prevents network failures when SvelteKit
// server-renders pages inside the container where localhost:PORT isn't mapped.
import { browser } from '$app/environment';
import { showNotification } from './stores/notifications';
import { session, getToken } from './stores/session';

const BASE = browser
  ? (import.meta.env.VITE_API_URL as string ||
    `${window.location.protocol}//${window.location.hostname}:8000`)
  : (import.meta.env.VITE_INTERNAL_API_URL as string || 'http://api:8000');

let isHandlingLogout = false;

async function req<T>(method: string, path: string, body?: unknown, opts?: { silent?: boolean }): Promise<T> {
  const silent = opts?.silent ?? false;
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
      if (!isHandlingLogout) {
        isHandlingLogout = true;
        session.logout();
        showNotification('Sesión expirada. Por favor, vuelve a iniciar sesión.', 'error');
      }
      throw new Error(`API ${method} ${path} → 401 Unauthorized`);
    }

    if (!res.ok) {
      const raw = await res.text().catch(() => res.statusText);
      // Parse JSON error bodies to extract a human-readable message instead
      // of showing raw JSON like {"detail":"VAPID not configured"} (#252).
      let userMsg = raw || res.statusText || 'Error desconocido';
      try {
        const parsed = JSON.parse(raw);
        userMsg = parsed.detail || parsed.message || parsed.error || raw;
      } catch { /* not JSON, use raw text */ }

      // Map non-actionable server errors to friendlier messages
      if (res.status === 502 || res.status === 503) {
        userMsg = 'El servicio no está disponible temporalmente.';
      }

      if (!silent) {
        showNotification(userMsg, 'error');
      }
      throw new Error(`API ${method} ${path} → ${res.status}: ${raw}`);
    }

    if (res.status === 204) return undefined as T;
    return res.json();
  } catch (error: any) {
    if (!silent && (error.name === 'TypeError' || error.message.includes('Failed to fetch') || error.message.includes('fetch failed'))) {
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

export interface EmbeddingFailure {
  note_id: number;
  attempts: number;
  last_error: string;
  updated_at: string | null;
  note_title?: string | null;
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

export interface SyncConflict {
  note_id: number;
  title: string;
  source_path: string;
  local_mtime: string | null;
  remote_mtime: string | null;
  last_synced_at: string | null;
}

export const api = {
  auth: {
    login: (password: string, username = 'user') => 
      req<{ access_token: string; token_type: string }>('POST', `/auth/login?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`),
    status: () => 
      req<{ enabled: boolean; has_password: boolean }>('GET', '/auth/status')
  },
  
  notes: {
    list:   (tag?: string, limit = 1000) => req<Note[]>('GET', `/notes/?limit=${limit}${tag ? `&tag=${encodeURIComponent(tag)}` : ''}`),
    get:    (id: number)   => req<Note>('GET', `/notes/${id}`),
    create: (data: { title: string; content: string; tags: string[]; source_path?: string | null; source?: string }) =>
      req<Note & { gamification: GamificationResult }>('POST', '/notes/', data),
    update: (id: number, data: Partial<{ title: string; content: string; tags: string[]; source_path: string | null }>) =>
      req<Note & { gamification: GamificationResult }>('PUT', `/notes/${id}`, data),
    delete: (id: number)   => req<void>('DELETE', `/notes/${id}`),
    bulkDelete: (ids: number[]) => req<{ deleted: number; total: number }>('POST', '/notes/bulk-delete', { ids }),
    bulkTag: (ids: number[], tags: string[]) => req<{ added: number; notes: number; tags: string[] }>('POST', '/notes/bulk-tag', { ids, tags }),
    bulkUntag: (ids: number[], tags: string[]) => req<{ removed: number; notes: number; tags: string[] }>('POST', '/notes/bulk-untag', { ids, tags }),
    acceptTag: (noteId: number, tag: string) =>
      req<{ tag: string; gamification: GamificationResult }>('POST', `/notes/${noteId}/accept-tag?tag_name=${encodeURIComponent(tag)}`),
    backlinks: (id: number) => req<Note[]>('GET', `/notes/${id}/backlinks`),
    similar: (id: number, limit = 5) => req<{ note: Note; score: number }[]>('GET', `/notes/${id}/similar?limit=${limit}`),
    semanticSearch: (query: string, limit = 10, threshold = 0.3) =>
      req<{ results: { note: Note; score: number }[] }>('POST', '/notes/search/semantic', { query, limit, threshold }),
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
    list:     (skip?: number, limit?: number) => req<Goal[]>('GET', `/goals/${skip !== undefined || limit !== undefined ? `?${skip !== undefined ? `skip=${skip}&` : ''}${limit !== undefined ? `limit=${limit}` : ''}` : ''}`),
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
      req<{ note_id: number; status: string; suggestions: AISuggestion[] }>('POST', '/ai/classify', { note_id: noteId, content, existing_tags: existingTags }, { silent: true }),
    usage: () => req<{ ai_enabled: boolean; estimated_cost_usd: number }>('GET', '/ai/usage'),
    dailyRecap: (date?: string) =>
      req<{ status: string; recap: string; suggestions: string[]; provider?: string }>('POST', `/ai/daily-recap${date ? `?target_date=${encodeURIComponent(date)}` : ''}`),
    cluster: (eps = 0.3, minSamples = 3, maxNotes = 500) =>
      req<{ clusters: { cluster_id: number; note_ids: number[]; note_count: number; representative_title: string; titles: string[] }[]; total_notes: number; noise_count: number; error?: string }>('POST', `/ai/cluster?eps=${eps}&min_samples=${minSamples}&max_notes=${maxNotes}`),
  },

github: {
    status: () => req<{ connected: boolean; username: string | null }>('GET', '/integrations/github/status'),
    issues: (filter: string = 'all') => req<{ issues: { id: number; number: number; title: string; repo: string; url: string; state: string; updated_at: string; author?: string }[]; stats: { total: number; open: number; closed: number }; filter: string }>('GET', `/integrations/github/issues?filter=${filter}`),
    pulls: (filter: string = 'all') => req<{ pulls: { id: number; number: number; title: string; repo: string; url: string; state: string; draft: boolean; updated_at: string; author?: string }[]; stats: { total: number; open: number; closed: number; draft: number }; filter: string }>('GET', `/integrations/github/pulls?filter=${filter}`),
    repos: () => req<{ repos: { id: number; name: string; full_name: string; color: string }[] }>('GET', '/integrations/github/repos'),
    startDeviceAuth: () => req<{ device_code: string; user_code: string; verification_uri: string; verification_uri_secondary?: string; expires_in: number; interval: number }>('GET', '/integrations/github/oauth/device/start'),
    pollDeviceCode: (device_code: string) => req<{ status: 'authorized'; access_token: string; token_type: string; scope: string } | { status: 'pending' | 'slowdown' | 'expired' | 'denied'; message: string }>('POST', `/integrations/github/oauth/device/polling?device_code=${encodeURIComponent(device_code)}`),
    startWebFlow: () => req<{ authorize_url: string; redirect_uri: string }>('GET', '/integrations/github/oauth/web/start'),
    oauthCallback: (code: string, state?: string) => req<{ status: string; access_token: string; token_type: string; scope: string }>('GET', `/integrations/github/oauth/callback?code=${encodeURIComponent(code)}${state ? `&state=${encodeURIComponent(state)}` : ''}`),
    revoke: () => req<{ status: string }>('POST', '/integrations/github/oauth/revoke'),
  },

  google: {
    authUrl: () => req<{ url: string }>('GET', '/integrations/google/auth'),
    connect: (code: string) =>
      req<{ status: string; scope: string | null }>('POST', '/integrations/google/connect', { code }),
    status: () => req<{ connected: boolean }>('GET', '/integrations/google/status'),
    disconnect: () => req<{ status: string }>('POST', '/integrations/google/disconnect'),
  },

  config: {
    setupStatus: () => req<{ needs_setup: boolean }>('GET', '/config/setup-status'),
    setup: (auth_password: string, obsidian_vault_path?: string) => 
      req<{ status: string; message: string }>('POST', '/config/setup', { auth_password, obsidian_vault_path }),

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
  
  embeddings: {
    deadLetters: (limit = 50) => req<EmbeddingFailure[]>('GET', `/notes/embeddings/dead-letters?limit=${limit}`),
    resetDeadLetter: (noteId: number) => req<{ status: string; note_id: number }>('POST', `/notes/embeddings/dead-letters/${noteId}/reset`),
    purgeDeadLetters: () => req<{ purged: number }>('DELETE', '/notes/embeddings/dead-letters'),
  },

  folders: {
    create: async (path: string) => {
      return req('POST', '/folders/', { path });
    },
    delete: async (path: string) => {
      return req('DELETE', `/folders/${encodeURIComponent(path)}`);
    }
  },

  upload: {
    image: async (file: File) => {
      const form = new FormData();
      form.append('file', file);
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${BASE}/upload/image`, { method: 'POST', headers, body: form });
      if (!res.ok) {
        const err = await res.text().catch(() => res.statusText);
        throw new Error(`Upload failed: ${res.status} ${err}`);
      }
      const result = await res.json() as { url: string; filename: string; mime: string; size: number };
      result.url = result.url.startsWith('http') ? result.url : `${BASE}${result.url}`;
      return result;
    },
    file: async (file: File) => {
      const form = new FormData();
      form.append('file', file);
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${BASE}/upload/file`, { method: 'POST', headers, body: form });
      if (!res.ok) {
        const err = await res.text().catch(() => res.statusText);
        throw new Error(`Upload failed: ${res.status} ${err}`);
      }
      const result = await res.json() as { url: string; filename: string; mime: string; size: number };
      result.url = result.url.startsWith('http') ? result.url : `${BASE}${result.url}`;
      return result;
    },
  },

  push: {
    vapidPublicKey: () =>
      req<{ publicKey: string }>('GET', '/push/vapid-public-key'),
    subscribe: (endpoint: string, keys: { p256dh: string; auth: string }) =>
      req<{ status: string }>('POST', '/push/subscribe', { endpoint, keys }),
    unsubscribe: () =>
      req<{ status: string }>('POST', '/push/unsubscribe'),
    test: (title: string, body: string) =>
      req<{ status: string }>('POST', '/push/test', { title, body }),
  },

  sync: {
    conflicts: () =>
      req<{ conflicts: SyncConflict[]; count: number }>('GET', '/sync/conflicts'),
    resolve: (noteId: number, resolution: string, mergedContent?: string) =>
      req<{ status: string; note_id: number; resolution: string }>('POST', `/sync/resolve/${noteId}`, { resolution, merged_content: mergedContent ?? null }),
  },
};
