import { writable, derived, get } from 'svelte/store';
import { api, type GamificationStats, type GamificationResult as GamificationResultType } from '$lib/api';
import { logger } from '$lib/utils/logger';
import { routeCache } from './routeCache';

const GAMIFICATION_CACHE_KEY = '/dashboard/gamification';

export const totalXP       = writable(0);
export const currentStreak = writable(0);
export const longestStreak = writable(0);
export const plantStage     = writable(0);
export const plantStageName = writable<string>('semilla');
export const nextStageXP    = writable<number | null>(100);
export const xpToNextStage  = writable<number | null>(100);
export const lastActivity   = writable<string | null>(null);

export const xpEvents = writable<{ amount: number; id: string; x?: number; y?: number }[]>([]);

// Must match PLANT_STAGES thresholds in api/services/gamification_engine.py
const STAGE_THRESHOLDS = [0, 300, 1200, 4000, 10000, 25000, 60000];

export const plantProgress = derived(
  [totalXP, nextStageXP, plantStage],
  ([$xp, $next, $stage]) => {
    if ($next === null) return 100;
    const prev = STAGE_THRESHOLDS[$stage] ?? 0;
    const range = ($next - prev) || 1;
    return Math.min(100, Math.round((($xp - prev) / range) * 100));
  }
);

export const MAX_XP = 60000;

export const globalProgress = derived(
  totalXP,
  $xp => Math.min(100, ($xp / MAX_XP) * 100)
);

export const globalLevel = derived(
  globalProgress,
  $prog => Math.min(100, Math.floor($prog) + 1)
);

export async function loadStats(): Promise<void> {
  // Try cache first for instant display
  const cached = routeCache.get<GamificationStats>(GAMIFICATION_CACHE_KEY);
  if (cached) {
    applyStats(cached);
  }

  try {
    const stats: GamificationStats = await api.gamification.stats();
    applyStats(stats);
    routeCache.set(GAMIFICATION_CACHE_KEY, stats);
  } catch (e) {
    logger.error('[gamification] Failed to load stats:', e);
  }
}

export async function pingActivity(): Promise<void> {
  try {
    const result = await api.gamification.ping();
    const stats: Partial<GamificationStats> = {
      total_xp: result.total_xp,
      current_streak: result.current_streak,
      longest_streak: result.longest_streak ?? get(longestStreak),
      plant_stage: result.plant_stage,
      plant_stage_name: result.plant_stage_name,
      next_stage_xp: result.next_stage_xp ?? get(nextStageXP),
      xp_to_next_stage: result.xp_to_next_stage ?? get(xpToNextStage),
      last_activity_date: result.last_activity_date ?? null,
    };
    applyStats(stats);
    routeCache.set(GAMIFICATION_CACHE_KEY, { ...getFullStats(), ...stats } as GamificationStats);
    if (result.xp_awarded > 0) {
      showXPGain(result.xp_awarded);
    }
  } catch (e) {
    logger.error('[gamification] pingActivity failed:', e);
  }
}

function getFullStats(): GamificationStats {
  return {
    total_xp: get(totalXP),
    current_streak: get(currentStreak),
    longest_streak: get(longestStreak),
    plant_stage: get(plantStage),
    plant_stage_name: get(plantStageName),
    next_stage_xp: get(nextStageXP),
    xp_to_next_stage: get(xpToNextStage),
    last_activity_date: get(lastActivity),
  };
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

import { notifications, showNotification, dismissNotification } from './notifications';
export { notifications, showNotification, dismissNotification };

export function applyGamificationResult(result: GamificationResultType): void {
  const prevStage = get(plantStage);
  
  totalXP.set(result.total_xp);
  currentStreak.set(result.current_streak);
  plantStage.set(result.plant_stage);
  plantStageName.set(result.plant_stage_name);
  
  if (result.xp_awarded > 0) {
    showXPGain(result.xp_awarded);
  }

  if (result.plant_stage_changed || result.plant_stage > prevStage) {
    showNotification(`🌱 ¡Tu planta ha evolucionado a ${result.plant_stage_name.toUpperCase()}!`, 'level');
  }

  if (result.streak_changed && result.current_streak > 0) {
    showNotification(`🔥 ¡Racha de ${result.current_streak} días!`, 'success');
  }
}

