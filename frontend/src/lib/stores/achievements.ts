import { writable, get } from 'svelte/store';

export interface Achievement {
  id: string;
  title: string;
  description: string;
  icon: string;
  unlocked: boolean;
  unlockedAt?: string;
}

const ACHIEVEMENTS_CONFIG: Omit<Achievement, 'unlocked' | 'unlockedAt'>[] = [
  { id: 'first_note', title: 'Primera Nota', description: 'Crea tu primera nota', icon: 'FileText' },
  { id: 'ten_notes', title: 'Coleccionista', description: 'Crea 10 notas', icon: 'Files' },
  { id: 'fifty_notes', title: 'Bibliotecario', description: 'Crea 50 notas', icon: 'Library' },
  { id: 'first_goal', title: 'Objetivo', description: 'Crea tu primera meta', icon: 'Target' },
  { id: 'goal_completed', title: 'Exitoso', description: 'Completa una meta', icon: 'CheckCircle' },
  { id: 'week_streak', title: 'Consistente', description: '7 días de racha', icon: 'Flame' },
  { id: 'month_streak', title: 'Dedicado', description: '30 días de racha', icon: 'Trophy' },
  { id: 'first_tag', title: 'Organizador', description: 'Crea tu primera etiqueta', icon: 'Tag' },
  { id: 'ten_skills', title: 'Aprendiz', description: 'Desbloquea 10 habilidades', icon: 'Zap' },
  { id: 'plant_sprout', title: 'Germinación', description: 'Tu planta reacha la etapa de brote', icon: 'Sprout' },
  { id: 'plant_tree', title: 'Árbol', description: 'Tu planta reacha la etapa de árbol', icon: 'TreeDeciduous' },
];

const STORAGE_KEY = 'joidy-achievements';

function loadAchievements(): Achievement[] {
  if (typeof localStorage === 'undefined') return [];
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const unlocked = JSON.parse(saved) as Record<string, string>;
      return ACHIEVEMENTS_CONFIG.map(a => ({
        ...a,
        unlocked: !!unlocked[a.id],
        unlockedAt: unlocked[a.id] || undefined,
      }));
    }
  } catch {}
  return ACHIEVEMENTS_CONFIG.map(a => ({ ...a, unlocked: false }));
}

function saveAchievements(achievements: Achievement[]) {
  if (typeof localStorage === 'undefined') return;
  const unlocked: Record<string, string> = {};
  achievements.forEach(a => {
    if (a.unlocked && a.unlockedAt) {
      unlocked[a.id] = a.unlockedAt;
    }
  });
  localStorage.setItem(STORAGE_KEY, JSON.stringify(unlocked));
}

function createAchievementsStore() {
  const { subscribe, set, update } = writable<Achievement[]>(loadAchievements());

  return {
    subscribe,
    init() {
      set(loadAchievements());
    },
    unlock(achievementId: string) {
      update(achievements => {
        const idx = achievements.findIndex(a => a.id === achievementId);
        if (idx !== -1 && !achievements[idx].unlocked) {
          const updated = [...achievements];
          updated[idx] = {
            ...updated[idx],
            unlocked: true,
            unlockedAt: new Date().toISOString(),
          };
          saveAchievements(updated);
          return updated;
        }
        return achievements;
      });
    },
    getUnlockedCount(): number {
      return get({ subscribe }).filter(a => a.unlocked).length;
    },
    isUnlocked(achievementId: string): boolean {
      return get({ subscribe }).find(a => a.id === achievementId)?.unlocked || false;
    },
  };
}

export const achievements = createAchievementsStore();

export function checkAndUnlockAchievement(
  condition: 'note_count' | 'goal_completed' | 'streak_days' | 'tag_count' | 'skill_count' | 'plant_stage',
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