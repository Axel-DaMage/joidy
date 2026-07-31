import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

// Mock $lib/api before importing the store. The factory returns a mutable api
// object so individual tests can override methods. Use vi.hoisted so the mock
// object is initialised before the hoisted vi.mock factory runs.
const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    gamification: {
      stats: vi.fn(),
      ping: vi.fn(),
    },
  },
}));

vi.mock('$lib/api', () => ({ api: apiMock }));

// Mock logger so it never touches the real environment detection.
vi.mock('$lib/utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), log: vi.fn(), debug: vi.fn() },
}));

// routeCache uses localStorage via $app/environment; mock it to a no-op cache.
vi.mock('./routeCache', () => ({
  routeCache: {
    get: vi.fn(() => null),
    set: vi.fn(),
    invalidate: vi.fn(),
    load: vi.fn(),
    getOrFetch: vi.fn(),
    prefetch: vi.fn(),
    cache: { subscribe: vi.fn(), set: vi.fn(), update: vi.fn() },
  },
}));

import {
  totalXP,
  currentStreak,
  longestStreak,
  plantStage,
  plantStageName,
  nextStageXP,
  xpToNextStage,
  lastActivity,
  xpEvents,
  plantProgress,
  globalProgress,
  globalLevel,
  loadStats,
  pingActivity,
  applyStats,
  applyGamificationResult,
  showXPGain,
} from './gamification';
import { notifications } from './notifications';

function resetStores() {
  totalXP.set(0);
  currentStreak.set(0);
  longestStreak.set(0);
  plantStage.set(0);
  plantStageName.set('semilla');
  nextStageXP.set(100);
  xpToNextStage.set(100);
  lastActivity.set(null);
  xpEvents.set([]);
  notifications.set([]);
}

describe('gamification store — initial state', () => {
  beforeEach(() => resetStores());

  it('starts with zero XP and the semilla stage', () => {
    expect(get(totalXP)).toBe(0);
    expect(get(currentStreak)).toBe(0);
    expect(get(longestStreak)).toBe(0);
    expect(get(plantStage)).toBe(0);
    expect(get(plantStageName)).toBe('semilla');
    expect(get(nextStageXP)).toBe(100);
    expect(get(xpToNextStage)).toBe(100);
    expect(get(lastActivity)).toBeNull();
  });
});

describe('applyStats', () => {
  beforeEach(() => resetStores());

  it('updates all provided fields', () => {
    applyStats({
      total_xp: 1500,
      current_streak: 4,
      longest_streak: 9,
      plant_stage: 2,
      plant_stage_name: 'planton',
      next_stage_xp: 4000,
      xp_to_next_stage: 2500,
      last_activity_date: '2024-01-02',
    });
    expect(get(totalXP)).toBe(1500);
    expect(get(currentStreak)).toBe(4);
    expect(get(longestStreak)).toBe(9);
    expect(get(plantStage)).toBe(2);
    expect(get(plantStageName)).toBe('planton');
    expect(get(nextStageXP)).toBe(4000);
    expect(get(xpToNextStage)).toBe(2500);
    expect(get(lastActivity)).toBe('2024-01-02');
  });

  it('ignores undefined fields and keeps existing values', () => {
    applyStats({ total_xp: 500 });
    expect(get(totalXP)).toBe(500);
    expect(get(currentStreak)).toBe(0);
    expect(get(plantStageName)).toBe('semilla');
  });

  it('does not overwrite plant_stage_name when not provided', () => {
    applyStats({ plant_stage_name: 'brote' });
    expect(get(plantStageName)).toBe('brote');
    applyStats({ total_xp: 10 });
    expect(get(plantStageName)).toBe('brote');
  });
});

describe('plant stage transitions', () => {
  beforeEach(() => resetStores());

  it('semilla -> brote at 300 XP', () => {
    applyStats({ total_xp: 300, plant_stage: 1, plant_stage_name: 'brote', next_stage_xp: 1200 });
    expect(get(plantStageName)).toBe('brote');
    expect(get(plantStage)).toBe(1);
  });

  it('brote -> planton at 1200 XP', () => {
    applyStats({ total_xp: 1200, plant_stage: 2, plant_stage_name: 'planton', next_stage_xp: 4000 });
    expect(get(plantStageName)).toBe('planton');
  });

  it('planton -> joven at 4000 XP', () => {
    applyStats({ total_xp: 4000, plant_stage: 3, plant_stage_name: 'joven', next_stage_xp: 10000 });
    expect(get(plantStageName)).toBe('joven');
  });

  it('joven -> madura at 10000 XP', () => {
    applyStats({ total_xp: 10000, plant_stage: 4, plant_stage_name: 'madura', next_stage_xp: 25000 });
    expect(get(plantStageName)).toBe('madura');
  });

  it('madura -> floreciendo at 25000 XP', () => {
    applyStats({ total_xp: 25000, plant_stage: 5, plant_stage_name: 'floreciendo', next_stage_xp: 60000 });
    expect(get(plantStageName)).toBe('floreciendo');
  });

  it('floreciendo -> arbol at 60000 XP', () => {
    applyStats({ total_xp: 60000, plant_stage: 6, plant_stage_name: 'arbol', next_stage_xp: null });
    expect(get(plantStageName)).toBe('arbol');
    expect(get(nextStageXP)).toBeNull();
  });
});

describe('derived stores', () => {
  beforeEach(() => resetStores());

  it('plantProgress is 100 when nextStageXP is null', () => {
    applyStats({ total_xp: 60000, plant_stage: 6, next_stage_xp: null });
    expect(get(plantProgress)).toBe(100);
  });

  it('plantProgress computes percentage within current stage range', () => {
    // stage 0: prev=0, next=100, xp=50 -> 50%
    applyStats({ total_xp: 50, plant_stage: 0, next_stage_xp: 100 });
    expect(get(plantProgress)).toBe(50);
  });

  it('plantProgress caps at 100', () => {
    applyStats({ total_xp: 500, plant_stage: 0, next_stage_xp: 100 });
    expect(get(plantProgress)).toBe(100);
  });

  it('globalProgress is xp / 60000 * 100 capped at 100', () => {
    applyStats({ total_xp: 30000 });
    expect(get(globalProgress)).toBeCloseTo(50, 1);
    applyStats({ total_xp: 120000 });
    expect(get(globalProgress)).toBe(100);
  });

  it('globalLevel is floor(progress) + 1 capped at 100', () => {
    applyStats({ total_xp: 30000 });
    expect(get(globalLevel)).toBe(51);
    applyStats({ total_xp: 120000 });
    expect(get(globalLevel)).toBe(100);
  });
});

describe('loadStats', () => {
  beforeEach(() => {
    resetStores();
    apiMock.gamification.stats.mockReset();
  });

  it('applies stats returned by the API', async () => {
    apiMock.gamification.stats.mockResolvedValue({
      total_xp: 750,
      current_streak: 2,
      longest_streak: 5,
      plant_stage: 1,
      plant_stage_name: 'brote',
      next_stage_xp: 1200,
      xp_to_next_stage: 450,
      last_activity_date: '2024-03-01',
    });
    await loadStats();
    expect(get(totalXP)).toBe(750);
    expect(get(plantStageName)).toBe('brote');
    expect(get(currentStreak)).toBe(2);
  });

  it('does not throw when the API fails', async () => {
    apiMock.gamification.stats.mockRejectedValue(new Error('network'));
    await expect(loadStats()).resolves.toBeUndefined();
    expect(get(totalXP)).toBe(0);
  });
});

describe('pingActivity', () => {
  beforeEach(() => {
    resetStores();
    apiMock.gamification.ping.mockReset();
  });

  it('applies ping result and shows XP gain when awarded', async () => {
    apiMock.gamification.ping.mockResolvedValue({
      xp_awarded: 15,
      total_xp: 115,
      current_streak: 1,
      plant_stage: 0,
      plant_stage_name: 'semilla',
      plant_stage_changed: false,
      streak_changed: true,
      milestone_reached: null,
      message: 'daily activity',
      next_stage_xp: 100,
      xp_to_next_stage: 0,
      last_activity_date: '2024-04-01',
    });
    await pingActivity();
    expect(get(totalXP)).toBe(115);
    expect(get(currentStreak)).toBe(1);
    expect(get(xpEvents).length).toBe(1);
    expect(get(xpEvents)[0].amount).toBe(15);
  });

  it('does not show XP event when no XP awarded', async () => {
    apiMock.gamification.ping.mockResolvedValue({
      xp_awarded: 0,
      total_xp: 100,
      current_streak: 1,
      plant_stage: 0,
      plant_stage_name: 'semilla',
      plant_stage_changed: false,
      streak_changed: false,
      milestone_reached: null,
      message: 'no gain',
    });
    await pingActivity();
    expect(get(xpEvents).length).toBe(0);
  });

  it('does not throw when the API fails', async () => {
    apiMock.gamification.ping.mockRejectedValue(new Error('boom'));
    await expect(pingActivity()).resolves.toBeUndefined();
  });
});

describe('applyGamificationResult', () => {
  beforeEach(() => resetStores());

  it('updates XP, streak and plant stage from a result', () => {
    applyGamificationResult({
      xp_awarded: 50,
      total_xp: 3050,
      current_streak: 7,
      plant_stage: 2,
      plant_stage_name: 'planton',
      plant_stage_changed: true,
      streak_changed: true,
      milestone_reached: 7,
      message: 'streak!',
    });
    expect(get(totalXP)).toBe(3050);
    expect(get(currentStreak)).toBe(7);
    expect(get(plantStage)).toBe(2);
    expect(get(plantStageName)).toBe('planton');
    expect(get(xpEvents).length).toBe(1);
  });

  it('shows a notification when the plant stage changed', () => {
    applyGamificationResult({
      xp_awarded: 10,
      total_xp: 310,
      current_streak: 0,
      plant_stage: 1,
      plant_stage_name: 'brote',
      plant_stage_changed: true,
      streak_changed: false,
      milestone_reached: null,
      message: 'evolved',
    });
    const notifs = get(notifications);
    expect(notifs.length).toBeGreaterThanOrEqual(1);
    expect(notifs.some(n => n.message.includes('brote'.toUpperCase()))).toBe(true);
  });

  it('shows a notification when the streak changed', () => {
    applyGamificationResult({
      xp_awarded: 5,
      total_xp: 5,
      current_streak: 3,
      plant_stage: 0,
      plant_stage_name: 'semilla',
      plant_stage_changed: false,
      streak_changed: true,
      milestone_reached: null,
      message: 'streak',
    });
    const notifs = get(notifications);
    expect(notifs.some(n => n.message.includes('3'))).toBe(true);
  });

  it('does not show stage notification when stage unchanged', () => {
    applyGamificationResult({
      xp_awarded: 5,
      total_xp: 5,
      current_streak: 0,
      plant_stage: 0,
      plant_stage_name: 'semilla',
      plant_stage_changed: false,
      streak_changed: false,
      milestone_reached: null,
      message: 'none',
    });
    const notifs = get(notifications);
    expect(notifs.every(n => !n.message.includes('evolucionado'))).toBe(true);
  });
});

describe('showXPGain', () => {
  beforeEach(() => resetStores());

  it('adds an XP event and removes it after the timeout', () => {
    vi.useFakeTimers();
    showXPGain(25);
    expect(get(xpEvents).length).toBe(1);
    expect(get(xpEvents)[0].amount).toBe(25);
    vi.advanceTimersByTime(2200);
    expect(get(xpEvents).length).toBe(0);
    vi.useRealTimers();
  });
});
