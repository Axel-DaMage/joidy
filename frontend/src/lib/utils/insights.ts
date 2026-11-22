/**
 * Deterministic, rule-based insights for the analytics dashboard (#1499).
 *
 * Each slide shows a side panel of plain-language findings computed from the
 * same /analytics/overview payload the chart uses. Functions are pure and
 * return i18n descriptors (key + interpolation values) — the InsightPanel
 * renders them through $t, so tests never touch the i18n runtime.
 *
 * Copy targets non-technical users: percentages and plain sentences, no
 * statistics jargon (z-scores and regressions stay inside the charts).
 */

import type { AnalyticsOverview } from '$lib/api';

export interface Insight {
  /** Lucide icon name (rendered via DynamicIcon). */
  icon: string;
  /** i18n key under `goalsAnalytics.insights.*`. */
  key: string;
  values?: Record<string, string | number>;
}

export interface InsightCtx {
  /** Translate helper (component's $t) for nested labels like XP type names. */
  t: (key: string, options?: { values?: Record<string, string | number> }) => string;
  /** Format an ISO date for display. */
  fmtDate: (iso: string) => string;
  /** Format weekday index (Mon=0..Sun=6) as a full weekday name. */
  fmtWeekday: (i: number) => string;
  /** Format an hour (0-23) for display, honoring 12/24h preference. */
  fmtHour: (h: number) => string;
}

type Overview = AnalyticsOverview;
type Day = Overview['daily_activity'][number];

const DAY_MS = 86_400_000;

/** Total XP per weekday index (Mon=0..Sun=6) from the daily series. */
export function xpByWeekday(activity: Day[]): number[] {
  const totals = [0, 0, 0, 0, 0, 0, 0];
  for (const d of activity) {
    const wd = (new Date(`${d.date}T00:00:00`).getDay() + 6) % 7;
    totals[wd] += d.xp;
  }
  return totals;
}

function argmax(arr: number[]): number {
  let best = 0;
  for (let i = 1; i < arr.length; i++) if (arr[i] > arr[best]) best = i;
  return best;
}

function pct(part: number, total: number): number {
  return total > 0 ? Math.round((part / total) * 100) : 0;
}

function deltaPct(current: number, previous: number): number | null {
  if (previous <= 0) return null;
  return Math.round(((current - previous) / previous) * 100);
}

// ── Consistency heatmap ──────────────────────────────────────────────────────

export function consistencyInsights(data: Overview, ctx: InsightCtx): Insight[] {
  const out: Insight[] = [];
  const { active_days } = data.summary;
  const total = data.days;
  const rate = total > 0 ? active_days / total : 0;

  out.push({
    icon: 'calendar-check',
    key: 'consistency.activeDays',
    values: { count: active_days, total },
  });

  const verdict =
    rate >= 0.7 ? 'consistency.verdictHigh' : rate >= 0.4 ? 'consistency.verdictMid' : 'consistency.verdictLow';
  out.push({ icon: rate >= 0.4 ? 'thumbs-up' : 'sprout', key: verdict });

  if (data.streaks.current_streak > 1) {
    out.push({
      icon: 'flame',
      key: 'consistency.currentStreak',
      values: { days: data.streaks.current_streak },
    });
  }
  if (data.streaks.longest_streak > 1) {
    out.push({
      icon: 'award',
      key: 'consistency.longestStreak',
      values: { days: data.streaks.longest_streak },
    });
  }
  const best = data.summary.best_day;
  if (best) {
    out.push({
      icon: 'trophy',
      key: 'consistency.bestDay',
      values: { date: ctx.fmtDate(best.date), xp: best.xp },
    });
  }
  return out;
}

// ── Productivity trend ───────────────────────────────────────────────────────

export function trendInsights(data: Overview, ctx: InsightCtx): Insight[] {
  const out: Insight[] = [];
  const s = data.summary;

  const delta = deltaPct(s.window_xp, s.prev_total_xp);
  if (delta === null) {
    out.push({ icon: 'sparkles', key: 'trend.firstWindow' });
  } else if (delta >= 10) {
    out.push({ icon: 'trending-up', key: 'trend.deltaUp', values: { pct: delta } });
  } else if (delta <= -10) {
    out.push({ icon: 'trending-down', key: 'trend.deltaDown', values: { pct: Math.abs(delta) } });
  } else {
    out.push({ icon: 'minus', key: 'trend.deltaFlat' });
  }

  const perWeekday = xpByWeekday(data.daily_activity);
  if (Math.max(...perWeekday) > 0) {
    out.push({
      icon: 'calendar',
      key: 'trend.bestWeekday',
      values: { day: ctx.fmtWeekday(argmax(perWeekday)) },
    });
  }

  if (s.best_day) {
    out.push({
      icon: 'trophy',
      key: 'trend.bestDay',
      values: { date: ctx.fmtDate(s.best_day.date), xp: s.best_day.xp },
    });
  }

  if (s.active_days > 0) {
    out.push({
      icon: 'zap',
      key: 'trend.avgActiveDay',
      values: { xp: Math.round(s.window_xp / s.active_days) },
    });
  }
  return out;
}

// ── Activity clock (seasonality) ─────────────────────────────────────────────

/** Sum seasonality cells per hour (0-23), optionally filtered by weekday. */
export function hoursFromCells(
  cells: { weekday: number; hour: number; count: number }[],
  weekdayFilter?: (weekday: number) => boolean
): number[] {
  const hours = new Array(24).fill(0);
  for (const c of cells) {
    if (!weekdayFilter || weekdayFilter(c.weekday)) hours[c.hour] += c.count;
  }
  return hours;
}

export function clockInsights(data: Overview, ctx: InsightCtx): Insight[] {
  const out: Insight[] = [];
  const cells = data.seasonality?.cells ?? [];
  if (cells.length === 0) return out;

  const perHour = hoursFromCells(cells);
  const totalEvents = perHour.reduce((a, b) => a + b, 0);
  if (totalEvents === 0) return out;

  const peakHour = argmax(perHour);
  out.push({ icon: 'clock', key: 'clock.peakHour', values: { hour: ctx.fmtHour(peakHour) } });

  const perWeekday = [0, 0, 0, 0, 0, 0, 0];
  for (const c of cells) perWeekday[c.weekday] += c.count;
  out.push({
    icon: 'calendar',
    key: 'clock.peakDay',
    values: { day: ctx.fmtWeekday(argmax(perWeekday)) },
  });

  // Time-of-day profile: morning 6-12, afternoon 12-18, evening 18-24, night 0-6.
  const bands = [
    { key: 'clock.bandNight', from: 0, to: 6 },
    { key: 'clock.bandMorning', from: 6, to: 12 },
    { key: 'clock.bandAfternoon', from: 12, to: 18 },
    { key: 'clock.bandEvening', from: 18, to: 24 },
  ];
  let top = bands[0];
  let topCount = 0;
  for (const b of bands) {
    const c = perHour.slice(b.from, b.to).reduce((a, x) => a + x, 0);
    if (c > topCount) {
      topCount = c;
      top = b;
    }
  }
  out.push({ icon: 'sun', key: top.key, values: { pct: pct(topCount, totalEvents) } });

  const weekdayCount = perWeekday.slice(0, 5).reduce((a, b) => a + b, 0);
  const weekendCount = perWeekday[5] + perWeekday[6];
  if (weekdayCount + weekendCount > 0) {
    const weekendShare = pct(weekendCount, weekdayCount + weekendCount);
    out.push({
      icon: 'briefcase',
      key: weekendShare >= 40 ? 'clock.moreWeekend' : 'clock.moreWeekdays',
      values: { pct: weekendShare >= 40 ? weekendShare : 100 - weekendShare },
    });
  }
  return out;
}

// ── Mood × XP ────────────────────────────────────────────────────────────────

export function moodInsights(data: Overview): Insight[] {
  const out: Insight[] = [];
  const m = data.mood_activity;
  if (!m || m.sample_size < 3 || m.pearson_r === null) {
    out.push({ icon: 'smile', key: 'mood.needMore' });
    return out;
  }
  out.push({
    icon: 'database',
    key: 'mood.samples',
    values: { count: m.sample_size },
  });
  const r = m.pearson_r;
  if (r >= 0.25) out.push({ icon: 'heart', key: 'mood.positive' });
  else if (r <= -0.25) out.push({ icon: 'cloud-rain', key: 'mood.negative' });
  else out.push({ icon: 'minus', key: 'mood.neutral' });
  return out;
}

// ── XP sources ───────────────────────────────────────────────────────────────

const XP_TYPE_KEY: [prefix: string, key: string][] = [
  ['goal_completed', 'goal_completed'],
  ['pomodoro_completed', 'pomodoro_completed'],
  ['note_created', 'note_created'],
  ['note_edited', 'note_edited'],
  ['daily_activity', 'daily_activity'],
  ['streak_milestone', 'streak_milestone'],
  ['calendar_task', 'calendar_task'],
  ['strava', 'strava'],
  ['tag', 'tag'],
  ['topic_connected', 'topic_connected'],
  ['note_imported_obsidian', 'note_imported_obsidian'],
  ['day_fully_planned', 'day_fully_planned'],
];

export function xpTypeLabel(type: string, ctx: InsightCtx): string {
  const hit = XP_TYPE_KEY.find(([prefix]) => type.startsWith(prefix));
  return hit ? ctx.t(`goalsAnalytics.xpTypes.${hit[1]}`) : type.replace(/_/g, ' ');
}

export function sourcesInsights(data: Overview, ctx: InsightCtx): Insight[] {
  const out: Insight[] = [];
  const rows = data.xp_by_type ?? [];
  const totalXp = rows.reduce((a, r) => a + r.xp, 0);
  const totalEvents = rows.reduce((a, r) => a + r.count, 0);
  if (rows.length === 0 || totalXp === 0) return out;

  const top = rows[0];
  const topShare = pct(top.xp, totalXp);
  out.push({
    icon: 'pie-chart',
    key: 'sources.topType',
    values: { name: xpTypeLabel(top.type, ctx), pct: topShare },
  });
  out.push({
    icon: topShare >= 60 ? 'focus' : 'shuffle',
    key: topShare >= 60 ? 'sources.concentrated' : 'sources.balanced',
  });
  out.push({ icon: 'activity', key: 'sources.events', values: { count: totalEvents } });
  return out;
}

// ── Goals ────────────────────────────────────────────────────────────────────

export function goalsInsights(data: Overview, ctx: InsightCtx): Insight[] {
  const out: Insight[] = [];
  const funnel = data.goals?.funnel ?? [];
  const count = (stage: string) => funnel.find((f) => f.stage === stage)?.count ?? 0;
  const activated = count('activated');
  const completed = count('completed');
  const abandoned = count('abandoned');

  if (activated > 0) {
    out.push({
      icon: 'circle-check',
      key: 'goals.completionRate',
      values: { pct: pct(completed, activated) },
    });
    if (abandoned > 0) {
      out.push({
        icon: 'archive',
        key: 'goals.abandonRate',
        values: { pct: pct(abandoned, activated) },
      });
    }
  }

  const temps = (data.goals?.by_temporality ?? []).filter((t) => t.completed + t.failed >= 2);
  if (temps.length > 0) {
    const best = temps.reduce((a, b) =>
      b.completed / (b.completed + b.failed) > a.completed / (a.completed + a.failed) ? b : a
    );
    out.push({
      icon: 'medal',
      key: 'goals.bestPeriod',
      values: {
        name: ctx.t(`goalsAnalytics.goals.temporalities.${best.temporality}`),
        pct: pct(best.completed, best.completed + best.failed),
      },
    });
  }

  const active = data.goals?.by_state?.ACTIVE ?? 0;
  if (active > 0) out.push({ icon: 'target', key: 'goals.active', values: { count: active } });
  return out;
}

// ── GitHub ───────────────────────────────────────────────────────────────────

export function githubInsights(data: Overview): Insight[] {
  const out: Insight[] = [];
  const weekly = data.github?.weekly ?? [];
  if (weekly.length === 0) return out;

  const totals = { pushes: 0, pull_requests: 0, issues: 0, comments: 0 };
  let busiestTotal = 0;
  for (const w of weekly) {
    const sum = w.pushes + w.pull_requests + w.issues + w.comments;
    if (sum > busiestTotal) busiestTotal = sum;
    totals.pushes += w.pushes;
    totals.pull_requests += w.pull_requests;
    totals.issues += w.issues;
    totals.comments += w.comments;
  }

  const dominant = (Object.entries(totals) as [keyof typeof totals, number][]).sort(
    (a, b) => b[1] - a[1]
  )[0];
  if (dominant && dominant[1] > 0) {
    out.push({
      icon: 'github',
      key: `github.top_${dominant[0]}`,
      values: { count: dominant[1] },
    });
  }
  if (busiestTotal > 0) {
    out.push({
      icon: 'calendar',
      key: 'github.busiestWeek',
      values: { count: busiestTotal },
    });
  }
  return out;
}

// ── Dispatcher ───────────────────────────────────────────────────────────────

export function insightsFor(slideId: string, data: Overview, ctx: InsightCtx): Insight[] {
  switch (slideId) {
    case 'consistency':
      return consistencyInsights(data, ctx);
    case 'trend':
      return trendInsights(data, ctx);
    case 'seasonality':
      return clockInsights(data, ctx);
    case 'mood':
      return moodInsights(data);
    case 'sources':
      return sourcesInsights(data, ctx);
    case 'goals':
      return goalsInsights(data, ctx);
    case 'github':
      return githubInsights(data);
    default:
      return [];
  }
}

export { DAY_MS };
