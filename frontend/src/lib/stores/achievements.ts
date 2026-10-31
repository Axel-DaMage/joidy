import { writable, get } from 'svelte/store';
import { browser } from '$app/env';
import { api } from '$lib/api';
import { getToken, session } from '$lib/stores/session';
import { logger } from '$lib/utils/logger';

export interface Achievement {
  id: string;
  title: string;
  description: string;
  icon: string;
  unlocked: boolean;
  unlockedAt?: string;
}

const ACHIEVEMENTS_CONFIG: Omit<Achievement, 'unlocked' | 'unlockedAt'>[] = [
  {
    id: 'first_note',
    title: 'Primera Nota',
    description: 'Crea tu primera nota',
    icon: 'FileText',
  },
  { id: 'ten_notes', title: 'Coleccionista', description: 'Crea 10 notas', icon: 'Files' },
  { id: 'fifty_notes', title: 'Bibliotecario', description: 'Crea 50 notas', icon: 'Library' },
  { id: 'first_goal', title: 'Objetivo', description: 'Crea tu primera meta', icon: 'Target' },
  {
    id: 'goal_completed',
    title: 'Exitoso',
    description: 'Completa una meta',
    icon: 'CircleCheckBig',
  },
  { id: 'week_streak', title: 'Consistente', description: '7 días de racha', icon: 'Flame' },
  { id: 'month_streak', title: 'Dedicado', description: '30 días de racha', icon: 'Trophy' },
  { id: 'first_tag', title: 'Organizador', description: 'Crea tu primera etiqueta', icon: 'Tag' },
  { id: 'ten_skills', title: 'Aprendiz', description: 'Desbloquea 10 habilidades', icon: 'Zap' },
  {
    id: 'plant_sprout',
    title: 'Germinación',
    description: 'Tu planta reacha la etapa de brote',
    icon: 'Sprout',
  },
  {
    id: 'plant_tree',
    title: 'Árbol',
    description: 'Tu planta reacha la etapa de árbol',
    icon: 'TreeDeciduous',
  },
];

const STORAGE_KEY = 'joidy-achievements';

type UnlockMap = Record<string, string>;

function loadLocalUnlocked(): UnlockMap {
  if (!browser) return {};
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      return JSON.parse(saved) as UnlockMap;
    }
  } catch {}
  return {};
}

function saveLocalUnlocked(map: UnlockMap) {
  if (!browser) return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
}

function toUnlockMap(achievements: Achievement[]): UnlockMap {
  const map: UnlockMap = {};
  achievements.forEach((a) => {
    if (a.unlocked && a.unlockedAt) {
      map[a.id] = a.unlockedAt;
    }
  });
  return map;
}

function toAchievements(map: UnlockMap): Achievement[] {
  return ACHIEVEMENTS_CONFIG.map((a) => ({
    ...a,
    unlocked: !!map[a.id],
    unlockedAt: map[a.id] || undefined,
  }));
}

function emptyAchievements(): Achievement[] {
  return ACHIEVEMENTS_CONFIG.map((a) => ({ ...a, unlocked: false }));
}

function createAchievementsStore() {
  const { subscribe, set, update } = writable<Achievement[]>(
    browser ? toAchievements(loadLocalUnlocked()) : emptyAchievements()
  );

  let syncing = false;
  let hadSession = false;
  let onlineHooked = false;

  async function pushUnlock(achievementId: string, unlockedAt?: string): Promise<boolean> {
    try {
      await api.achievements.unlock(achievementId, unlockedAt);
      return true;
    } catch (e) {
      logger.warn(`[achievements] Unlock "${achievementId}" not synced, kept locally:`, e);
      return false;
    }
  }

  async function sync(): Promise<void> {
    if (!browser || syncing) return;
    if (!getToken()) return;
    syncing = true;
    try {
      const records = await api.achievements.list();
      const merged: UnlockMap = {};
      for (const r of records) {
        if (r.unlocked_at) merged[r.achievement_key] = r.unlocked_at;
      }
      // Local unlocks absent from the server (offline unlocks or legacy
      // localStorage data) are pushed so the DB becomes authoritative.
      const local = loadLocalUnlocked();
      for (const [key, at] of Object.entries(local)) {
        if (!(key in merged)) {
          await pushUnlock(key, at);
        }
        merged[key] = merged[key] ?? at;
      }
      saveLocalUnlocked(merged);
      set(toAchievements(merged));
    } catch (e) {
      logger.warn('[achievements] Server sync failed, using local achievements:', e);
    } finally {
      syncing = false;
    }
  }

  function hookOnlineResync() {
    if (!browser || onlineHooked) return;
    onlineHooked = true;
    window.addEventListener('online', () => {
      sync().catch((e) => logger.error('[achievements] Online re-sync failed:', e));
    });
  }

  if (browser) {
    hookOnlineResync();
    // Sync when a session appears (app load with session or fresh login).
    session.subscribe((s) => {
      if (s && !hadSession) {
        hadSession = true;
        sync().catch((e) => logger.error('[achievements] Post-login sync failed:', e));
      } else if (!s) {
        hadSession = false;
      }
    });
  }

  return {
    subscribe,
    init() {
      set(browser ? toAchievements(loadLocalUnlocked()) : emptyAchievements());
    },
    unlock(achievementId: string) {
      let unlockedAt: string | undefined;
      update((achievements) => {
        const idx = achievements.findIndex((a) => a.id === achievementId);
        if (idx !== -1 && !achievements[idx].unlocked) {
          unlockedAt = new Date().toISOString();
          const updated = [...achievements];
          updated[idx] = {
            ...updated[idx],
            unlocked: true,
            unlockedAt,
          };
          saveLocalUnlocked(toUnlockMap(updated));
          return updated;
        }
        return achievements;
      });
      if (unlockedAt && browser && getToken()) {
        pushUnlock(achievementId, unlockedAt).catch((e) =>
          logger.error('[achievements] Unlock sync failed:', e)
        );
      }
    },
    getUnlockedCount(): number {
      return get({ subscribe }).filter((a) => a.unlocked).length;
    },
    isUnlocked(achievementId: string): boolean {
      return get({ subscribe }).find((a) => a.id === achievementId)?.unlocked || false;
    },
  };
}

export const achievements = createAchievementsStore();

export function checkAndUnlockAchievement(
  condition:
    'note_count' | 'goal_completed' | 'streak_days' | 'tag_count' | 'skill_count' | 'plant_stage',
  value: number
) {
  const rules: Record<string, number | string> = {
    note_count: 1,
    goal_completed: 1,
    streak_days: 7,
    tag_count: 1,
    skill_count: 10,
    plant_stage: 1,
  };

  const mapping: Record<string, string> = {
    '1': 'first_note',
    '10': 'ten_notes',
    '50': 'fifty_notes',
    'goal_completed-1': 'goal_completed',
    'streak_days-7': 'week_streak',
    'streak_days-30': 'month_streak',
    'tag_count-1': 'first_tag',
    'skill_count-10': 'ten_skills',
    'plant_stage-1': 'plant_sprout',
    'plant_stage-6': 'plant_tree',
  };

  const key = `${condition}-${value}`;
  const achievementId = mapping[key];
  if (achievementId) {
    achievements.unlock(achievementId);
  }
}
