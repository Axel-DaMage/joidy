import { describe, expect, it } from 'vitest';
import { consistencyInsights, trendInsights, clockInsights, type InsightCtx } from './insights';
import type { AnalyticsOverview } from '$lib/api';

const ctx: InsightCtx = {
  t: (key, opts) =>
    `${key}(${Object.entries(opts?.values ?? {})
      .map(([k, v]) => `${k}=${v}`)
      .join(',')})`,
  fmtDate: (iso) => iso,
  fmtWeekday: (i) => `wd${i}`,
  fmtHour: (h) => `${h}:00`,
};

function base(overrides: Partial<AnalyticsOverview> = {}): AnalyticsOverview {
  return {
    days: 7,
    daily_activity: [],
    xp_by_type: [],
    seasonality: { cells: [] },
    mood_activity: { points: [], correlation: null, samples: 0 },
    goals: { by_state: [], funnel: [], temporality: [] },
    streaks: {
      current_streak: 0,
      longest_streak: 0,
      active_streaks: 0,
      total_checkins: 0,
      checkin_rate_30d: null,
    },
    github: { available: false, weeks: [], types: [] },
    summary: {
      total_xp: 0,
      window_xp: 0,
      prev_total_xp: 0,
      prev_active_days: 0,
      active_days: 0,
      avg_daily_xp: 0,
      best_day: null,
    },
    ...overrides,
  } as AnalyticsOverview;
}

const daysAgo = (n: number, xp: number, events = 1) => ({
  date: new Date(Date.now() - n * 86400_000).toISOString().slice(0, 10),
  xp,
  events,
  goals_completed: 0,
  pomodoros: 0,
  notes: 0,
});

describe('trendInsights', () => {
  it('first-window flag when there is no previous data', () => {
    const items = trendInsights(
      base({ daily_activity: [daysAgo(0, 10)], summary: { ...base().summary, window_xp: 10 } }),
      ctx
    );
    expect(items[0].key).toBe('trend.firstWindow');
  });

  it('reports an up delta vs the previous period', () => {
    const items = trendInsights(
      base({
        daily_activity: [daysAgo(0, 20)],
        summary: { ...base().summary, window_xp: 200, prev_total_xp: 100, best_day: null },
      }),
      ctx
    );
    expect(items[0].key).toBe('trend.deltaUp');
    expect(items[0].values?.pct).toBe(100);
  });

  it('reports a down delta vs the previous period', () => {
    const items = trendInsights(
      base({
        daily_activity: [daysAgo(0, 5)],
        summary: { ...base().summary, window_xp: 50, prev_total_xp: 200, best_day: null },
      }),
      ctx
    );
    expect(items[0].key).toBe('trend.deltaDown');
    expect(items[0].values?.pct).toBe(75);
  });

  it('names the most productive weekday in user language', () => {
    // Mondays (weekday 0) carry the XP.
    const monday = new Date();
    monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7) - 7);
    const iso = monday.toISOString().slice(0, 10);
    const items = trendInsights(
      base({
        daily_activity: [
          { date: iso, xp: 99, events: 3, goals_completed: 0, pomodoros: 0, notes: 0 },
          daysAgo(0, 1),
        ],
        summary: { ...base().summary, window_xp: 100 },
      }),
      ctx
    );
    expect(items.some((i) => i.key === 'trend.bestWeekday')).toBe(true);
  });
});

describe('consistencyInsights', () => {
  it('verdict reflects coverage and includes streaks', () => {
    const items = consistencyInsights(
      base({
        summary: { ...base().summary, active_days: 4 },
        streaks: { ...base().streaks, current_streak: 3 },
      }),
      ctx
    );
    expect(items.map((i) => i.key)).toEqual([
      'consistency.activeDays',
      'consistency.verdictMid',
      'consistency.currentStreak',
    ]);
  });
});

describe('clockInsights', () => {
  it('reports peak hour and dominant band from seasonality cells', () => {
    const cells = [
      { weekday: 2, hour: 15, count: 10 },
      { weekday: 3, hour: 16, count: 5 },
    ];
    const items = clockInsights(base({ seasonality: { cells, max: 10 } }), ctx);
    const keys = items.map((i) => i.key);
    expect(keys).toContain('clock.peakHour');
    expect(keys).toContain('clock.peakDay');
    expect(keys).toContain('clock.bandAfternoon');
    expect(keys).toContain('clock.moreWeekdays');
  });
});
