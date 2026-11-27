import type { PersonalStreak } from '$lib/api';

/**
 * Status-bar streak pill evolution tiers (#1662). Boundaries mirror the
 * gamification milestones in api/services/gamification_engine.py
 * (7/30/100/365-day streak bonuses).
 */
export type StreakTier = 'seed' | 'sprout' | 'grown' | 'established' | 'legendary';

export const STREAK_TIER_THRESHOLDS = {
  sprout: 7,
  grown: 30,
  established: 100,
  legendary: 365,
} as const;

export function streakTierFor(days: number): StreakTier {
  if (days >= STREAK_TIER_THRESHOLDS.legendary) return 'legendary';
  if (days >= STREAK_TIER_THRESHOLDS.established) return 'established';
  if (days >= STREAK_TIER_THRESHOLDS.grown) return 'grown';
  if (days >= STREAK_TIER_THRESHOLDS.sprout) return 'sprout';
  return 'seed';
}

/** Glyph shown on the pill — legendary gets a distinct badge (#257:
 *  dynamic name → DynamicIcon). */
export function streakTierIcon(tier: StreakTier): string {
  return tier === 'legendary' ? 'Trophy' : 'Flame';
}

/** The longest-running active (non-archived) personal streak, or null. */
export function pickTopStreak(
  list: PersonalStreak[] | null | undefined
): PersonalStreak | null {
  if (!list) return null;
  return list.reduce<PersonalStreak | null>(
    (best, s) =>
      !s.is_archived && s.current_streak > (best?.current_streak ?? -1) ? s : best,
    null
  );
}
