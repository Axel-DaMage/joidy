import { writable, derived, get } from 'svelte/store';
import { api, type GamificationStats } from '$lib/api';

export const totalXP       = writable(0);
export const currentStreak = writable(0);
export const longestStreak = writable(0);
export const plantStage     = writable(0);
export const plantStageName = writable<string>('seed');
export const nextStageXP    = writable<number | null>(100);
export const xpToNextStage  = writable<number | null>(100);
export const lastActivity   = writable<string | null>(null);

export const xpEvents = writable<{ amount: number; id: string; x?: number; y?: number }[]>([]);

export const plantProgress = derived(
  [totalXP, nextStageXP],
  ([$xp, $next]) => {
    if ($next === null) return 100;
    const STAGES = [0, 100, 500, 1500, 4000, 10000, 25000];
    const stage = get(plantStage);
    const prev = STAGES[stage] ?? 0;
    const range = ($next - prev) || 1;
    return Math.min(100, Math.round((($xp - prev) / range) * 100));
  }
);

export async function loadStats(): Promise<void> {
  try {
    const stats: GamificationStats = await api.gamification.stats();
    applyStats(stats);
  } catch (e) {
    console.error('[gamification] Failed to load stats:', e);
  }
}

export async function pingActivity(): Promise<void> {
  try {
    const result = await api.gamification.ping();
    applyStats({
      total_xp: result.total_xp,
      current_streak: result.current_streak,
      longest_streak: get(longestStreak),
      plant_stage: result.plant_stage,
      plant_stage_name: result.plant_stage_name,
      next_stage_xp: get(nextStageXP),
      xp_to_next_stage: get(xpToNextStage),
      last_activity_date: null,
    });
    if (result.xp_awarded > 0) {
      showXPGain(result.xp_awarded);
    }
  } catch (_) {}
}

export function applyStats(stats: Partial<GamificationStats>): void {
  if (stats.total_xp !== undefined)       totalXP.set(stats.total_xp);
  if (stats.current_streak !== undefined) currentStreak.set(stats.current_streak);
  if (stats.longest_streak !== undefined) longestStreak.set(stats.longest_streak);
  if (stats.plant_stage !== undefined)    plantStage.set(stats.plant_stage);
  if (stats.plant_stage_name)             plantStageName.set(stats.plant_stage_name);
  if (stats.next_stage_xp !== undefined)  nextStageXP.set(stats.next_stage_xp);
  if (stats.xp_to_next_stage !== undefined) xpToNextStage.set(stats.xp_to_next_stage);
  if (stats.last_activity_date !== undefined) lastActivity.set(stats.last_activity_date);
}

export function showXPGain(amount: number, x?: number, y?: number): void {
  const id = `xp-${Date.now()}-${Math.random()}`;
  xpEvents.update(evts => [...evts, { amount, id, x, y }]);
  setTimeout(() => {
    xpEvents.update(evts => evts.filter(e => e.id !== id));
  }, 2200);
}

export function applyGamificationResult(result: { xp_awarded: number; total_xp: number; current_streak: number; plant_stage: number; plant_stage_name: string }): void {
  totalXP.set(result.total_xp);
  currentStreak.set(result.current_streak);
  plantStage.set(result.plant_stage);
  plantStageName.set(result.plant_stage_name);
  if (result.xp_awarded > 0) {
    showXPGain(result.xp_awarded);
  }
}
