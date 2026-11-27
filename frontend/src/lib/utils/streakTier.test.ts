import { describe, it, expect } from 'vitest';
import {
  STREAK_TIER_THRESHOLDS,
  streakTierFor,
  streakTierIcon,
  pickTopStreak,
} from './streakTier';
import type { PersonalStreak } from '$lib/api';

function makeStreak(overrides: Partial<PersonalStreak>): PersonalStreak {
  return {
    id: 1,
    name: 'streak',
    emoji: '',
    icon: 'Flame',
    description: '',
    color: '',
    theme: 'solid',
    category: '',
    start_date: null,
    target_date: null,
    offset: 0,
    frequency: 'daily',
    frequency_days: 1,
    is_archived: false,
    current_streak: 0,
    longest_streak: 0,
    best_streak: 0,
    total_checkins: 0,
    freeze_count: 0,
    freeze_used: 0,
    days_remaining: null,
    completion_pct: null,
    today_checked: false,
    history: [],
    created_at: '',
    ...overrides,
  };
}

describe('streakTierFor', () => {
  it('maps streak lengths to the gamification milestone tiers', () => {
    expect(streakTierFor(0)).toBe('seed');
    expect(streakTierFor(6)).toBe('seed');
    expect(streakTierFor(7)).toBe('sprout');
    expect(streakTierFor(29)).toBe('sprout');
    expect(streakTierFor(30)).toBe('grown');
    expect(streakTierFor(99)).toBe('grown');
    expect(streakTierFor(100)).toBe('established');
    expect(streakTierFor(364)).toBe('established');
    expect(streakTierFor(365)).toBe('legendary');
    expect(streakTierFor(1000)).toBe('legendary');
  });

  it('keeps thresholds aligned with gamification milestones (7/30/100/365)', () => {
    expect(STREAK_TIER_THRESHOLDS).toEqual({
      sprout: 7,
      grown: 30,
      established: 100,
      legendary: 365,
    });
  });
});

describe('streakTierIcon', () => {
  it('gives legendary a distinct glyph and the rest the flame', () => {
    expect(streakTierIcon('legendary')).toBe('Trophy');
    expect(streakTierIcon('seed')).toBe('Flame');
    expect(streakTierIcon('sprout')).toBe('Flame');
    expect(streakTierIcon('grown')).toBe('Flame');
    expect(streakTierIcon('established')).toBe('Flame');
  });
});

describe('pickTopStreak', () => {
  it('returns null for empty/missing lists', () => {
    expect(pickTopStreak(null)).toBeNull();
    expect(pickTopStreak(undefined)).toBeNull();
    expect(pickTopStreak([])).toBeNull();
  });

  it('picks the longest current streak', () => {
    const a = makeStreak({ id: 1, current_streak: 3 });
    const b = makeStreak({ id: 2, current_streak: 42 });
    const c = makeStreak({ id: 3, current_streak: 10 });
    expect(pickTopStreak([a, b, c])?.id).toBe(2);
    expect(pickTopStreak([c, b, a])?.id).toBe(2);
  });

  it('ignores archived streaks even when they are the longest', () => {
    const active = makeStreak({ id: 1, current_streak: 5 });
    const archived = makeStreak({ id: 2, current_streak: 400, is_archived: true });
    expect(pickTopStreak([active, archived])?.id).toBe(1);
    expect(pickTopStreak([archived])).toBeNull();
  });
});
