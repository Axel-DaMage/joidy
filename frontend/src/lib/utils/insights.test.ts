import { describe, expect, it } from 'vitest';
import {
  consistencyInsights,
  trendInsights,
  clockInsights,
  moodInsights,
  githubInsights,
  avgXpByWeekday,
  hoursFromCells,
  type InsightCtx,
} from './insights';
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
    mood_activity: { points: [], pearson_r: null, sample_size: 0 },
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
      { weekday: 2, hour: 15, count: 10, xp: 100 },
      { weekday: 3, hour: 16, count: 5, xp: 50 },
    ];
    const items = clockInsights(base({ seasonality: { cells, max: 10 } }), ctx);
    const keys = items.map((i) => i.key);
    expect(keys).toContain('clock.peakHour');
    expect(keys).toContain('clock.peakDay');
    expect(keys).toContain('clock.bandAfternoon');
    expect(keys).toContain('clock.moreWeekdays');
  });
});

describe('avgXpByWeekday', () => {
  it('averages per occurrence so uneven weekday counts stay comparable', () => {
    // 2024-01-01 is a Monday; two Mondays (10 + 30) and one Tuesday (6).
    const row = (date: string, xp: number) => ({
      date,
      xp,
      events: 1,
      goals_completed: 0,
      pomodoros: 0,
      notes: 0,
    });
    const avgs = avgXpByWeekday([row('2024-01-01', 10), row('2024-01-08', 30), row('2024-01-02', 6)]);
    expect(avgs[0]).toBe(20);
    expect(avgs[1]).toBe(6);
    expect(avgs[2]).toBe(0);
  });
});

describe('hoursFromCells', () => {
  it('uses XP when present and falls back to event count', () => {
    expect(hoursFromCells([{ weekday: 0, hour: 5, count: 9, xp: 40 }])[5]).toBe(40);
    expect(hoursFromCells([{ weekday: 0, hour: 5, count: 9 }])[5]).toBe(9);
  });
});

describe('insight headline stats', () => {
  it('consistency exposes the coverage as a stat with a tone', () => {
    const items = consistencyInsights(
      base({ days: 10, summary: { ...base().summary, active_days: 9 } }),
      ctx
    );
    expect(items[0].stat).toBe('9/10');
    expect(items[1].stat).toBe('90%');
    expect(items[1].tone).toBe('good');
  });

  it('mood without data explains how to unlock the analysis', () => {
    const keys = moodInsights(base()).map((i) => i.key);
    expect(keys).toEqual(['mood.needMore', 'mood.howTo', 'mood.unlock']);
  });
});

describe('githubInsights', () => {
  it('explains how to unlock the section when nothing is connected', () => {
    const keys = githubInsights(base()).map((i) => i.key);
    expect(keys).toEqual(['github.needConnect', 'github.howTo', 'github.unlock']);
  });

  it('points to a token when GitHub rate-limited the requests', () => {
    const data = base({
      github: { available: false, weekly: [], error: 'rate_limited' } as never,
    });
    const keys = githubInsights(data).map((i) => i.key);
    expect(keys).toEqual(['github.error_rate_limited', 'github.howToToken', 'github.unlock']);
  });

  it('summarises active weeks and totals when data exists', () => {
    const weekly = [
      { week_start: '2026-11-02', pushes: 3, pull_requests: 1, issues: 0, comments: 0 },
      { week_start: '2026-11-09', pushes: 0, pull_requests: 0, issues: 0, comments: 0 },
    ];
    const items = githubInsights(base({ github: { available: true, weekly } }));
    expect(items.find((i) => i.key === 'github.activeWeeks')?.stat).toBe('1/2');
    expect(items.find((i) => i.key === 'github.total')?.stat).toBe('4');
  });
});
