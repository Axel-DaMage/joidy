// API base URL — configurable via VITE_API_URL env var, defaults to localhost:8000
const BASE = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000';

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined
  });
  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText);
    throw new Error(`API ${method} ${path} → ${res.status}: ${err}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Note {
  id: number;
  title: string;
  content: string;
  source: string;
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
  plant_stage: number;
  plant_stage_name: string;
  plant_stage_changed: boolean;
  streak_changed: boolean;
  milestone_reached: number | null;
  message: string;
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
  target_notes: number;
  tag_id: number | null;
  progress: number;
  progress_pct: number;
  is_completed: boolean;
  completed_at: string | null;
  created_at: string;
}

export interface GraphNode { id: number; name: string; note_count: number; parent_id: number | null; }
export interface GraphEdge { source: number; target: number; type: 'hierarchy' | 'cooccurrence'; weight?: number; }
export interface GraphData { nodes: GraphNode[]; edges: GraphEdge[]; }

export interface AISuggestion { tag: string; confidence: number; is_new: boolean; }

// ── Notes ─────────────────────────────────────────────────────────────────────

export const api = {
  notes: {
    list:   (tag?: string) => req<Note[]>('GET', `/notes/${tag ? `?tag=${encodeURIComponent(tag)}` : ''}`),
    get:    (id: number)   => req<Note>('GET', `/notes/${id}`),
    create: (data: { title: string; content: string; tags: string[] }) =>
      req<Note & { gamification: GamificationResult }>('POST', '/notes/', data),
    update: (id: number, data: Partial<{ title: string; content: string; tags: string[] }>) =>
      req<Note & { gamification: GamificationResult }>('PUT', `/notes/${id}`, data),
    delete: (id: number)   => req<void>('DELETE', `/notes/${id}`),
    acceptTag: (noteId: number, tag: string) =>
      req<{ tag: string; gamification: GamificationResult }>('POST', `/notes/${noteId}/accept-tag?tag_name=${encodeURIComponent(tag)}`),
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
    create:   (data: { title: string; description?: string; target_notes?: number; tag_id?: number | null }) =>
      req<Goal>('POST', '/goals/', data),
    update:   (id: number, data: Partial<Goal>) => req<Goal>('PUT', `/goals/${id}`, data),
    complete: (id: number) =>
      req<{ goal: Goal; gamification: GamificationResult }>('POST', `/goals/${id}/complete`),
    delete:   (id: number) => req<void>('DELETE', `/goals/${id}`),
  },

  ai: {
    // AI is currently disabled — stub returns empty suggestions
    classify: async (_noteId: number, _content: string, _existingTags: string[]) =>
      ({ suggestions: [] as AISuggestion[] }),
    usage: async () => ({ ai_enabled: false, estimated_cost_usd: 0 }),
  },

  github: {
    status: () => req<{ connected: boolean; username: string | null }>('GET', '/integrations/github/status'),
    issues: () => req<{ id: number; number: number; title: string; repo: string; url: string; labels: string[]; updated_at: string }[]>('GET', '/integrations/github/issues'),
  },
};
