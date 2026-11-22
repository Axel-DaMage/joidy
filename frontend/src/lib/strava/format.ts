/**
 * Pure formatting + aggregation helpers for the Strava UI (#44).
 *
 * Kept free of Svelte/store imports so they run in vitest and can be unit
 * tested in isolation. Locale is passed explicitly (the caller reads the
 * `locale` store) so these stay deterministic.
 */

import type { StravaActivity, StravaSportTotals } from './types';

// ---------------------------------------------------------------------------
// Numbers / units
// ---------------------------------------------------------------------------

export interface UnitOptions {
  /** 'metric' → km/m; 'imperial' → mi/ft-ish (miles + feet for elevation). */
  unit?: 'metric' | 'imperial';
}

const METERS_PER_KM = 1000;
const METERS_PER_MILE = 1609.344;
const FEET_PER_METER = 3.28084;

function numFmt(locale: string): Intl.NumberFormat {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
}

function numFmt2(locale: string): Intl.NumberFormat {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
}

/**
 * Format a metric distance (meters) for display.
 * < 1 km → "850 m"; ≥ 1 km → "12.35 km" (2 decimals under 10 km, 1 above).
 */
export function formatDistance(
  meters: number | null | undefined,
  locale = 'es',
  opts: UnitOptions = {}
): string {
  if (meters == null || !Number.isFinite(meters)) return '—';
  if (opts.unit === 'imperial') {
    const miles = meters / METERS_PER_MILE;
    if (miles < 0.1) return `${Math.round(meters * FEET_PER_METER).toLocaleString(locale)} ft`;
    return `${numFmt2(locale).format(miles)} mi`;
  }
  if (meters < METERS_PER_KM) {
    return `${Math.round(meters).toLocaleString(locale)} m`;
  }
  const km = meters / METERS_PER_KM;
  return `${(km < 10 ? numFmt2(locale) : numFmt(locale)).format(km)} km`;
}

/** Format elevation gain (meters). */
export function formatElevation(
  meters: number | null | undefined,
  locale = 'es',
  opts: UnitOptions = {}
): string {
  if (meters == null || !Number.isFinite(meters)) return '—';
  if (opts.unit === 'imperial') {
    return `${Math.round(meters * FEET_PER_METER).toLocaleString(locale)} ft`;
  }
  return `${Math.round(meters).toLocaleString(locale)} m`;
}

/** Generic grouped number (calories, count, …). */
export function formatNumber(value: number | null | undefined, locale = 'es'): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return Math.round(value).toLocaleString(locale);
}

// ---------------------------------------------------------------------------
// Durations / pace
// ---------------------------------------------------------------------------

/**
 * Clock-style duration for a single activity: "45:12" under an hour,
 * "1:02:33" above. Strava shows moving_time this way.
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return '—';
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, '0');
  const ss = String(s).padStart(2, '0');
  return h > 0 ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
}

/**
 * Long-form duration for aggregate totals: "2 h 15 min" / "45 min" /
 * "30 s". Unit words are locale-neutral abbreviations to stay compact.
 */
export function formatDurationLong(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return '—';
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return m > 0 ? `${h} h ${m} min` : `${h} h`;
  if (m > 0) return s > 0 ? `${m} min ${s} s` : `${m} min`;
  return `${s} s`;
}

/**
 * Pace = moving_time / distance, rendered "5:30 /km" (metric) or
 * "8:45 /mi" (imperial). Returns null when distance/time are unusable so
 * callers can render a dash — pace is meaningless for 0 m.
 */
export function formatPace(
  movingTimeSec: number | null | undefined,
  distanceMeters: number | null | undefined,
  opts: UnitOptions = {}
): string | null {
  if (!movingTimeSec || !distanceMeters || distanceMeters <= 0 || movingTimeSec <= 0) {
    return null;
  }
  const imperial = opts.unit === 'imperial';
  const unitMeters = imperial ? METERS_PER_MILE : METERS_PER_KM;
  const secondsPerUnit = (movingTimeSec / distanceMeters) * unitMeters;
  const minutes = Math.floor(secondsPerUnit / 60);
  const seconds = Math.round(secondsPerUnit % 60);
  // Rounding can push seconds to 60 — normalize into the minute.
  const mm = minutes + (seconds === 60 ? 1 : 0);
  const ss = seconds === 60 ? 0 : seconds;
  return `${mm}:${String(ss).padStart(2, '0')} /${imperial ? 'mi' : 'km'}`;
}

/** Speed in km/h (or mph) from Strava's m/s `average_speed`. */
export function formatSpeed(
  metersPerSec: number | null | undefined,
  locale = 'es',
  opts: UnitOptions = {}
): string {
  if (metersPerSec == null || !Number.isFinite(metersPerSec) || metersPerSec <= 0) return '—';
  const value = opts.unit === 'imperial' ? metersPerSec * 2.23694 : metersPerSec * 3.6;
  return `${numFmt(locale).format(value)} ${opts.unit === 'imperial' ? 'mph' : 'km/h'}`;
}

// ---------------------------------------------------------------------------
// Dates
// ---------------------------------------------------------------------------

/** "12 mar" style short date for activity cards. */
export function formatActivityDate(iso: string | null | undefined, locale = 'es'): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString(locale, { day: '2-digit', month: 'short' });
}

/** Full date+time for the detail header. */
export function formatActivityDateTime(iso: string | null | undefined, locale = 'es'): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString(locale, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ---------------------------------------------------------------------------
// Sport classification
// ---------------------------------------------------------------------------

export type SportCategory =
  | 'run'
  | 'ride'
  | 'swim'
  | 'hike'
  | 'winter'
  | 'water'
  | 'strength'
  | 'other';

const SPORT_RULES: [SportCategory, RegExp][] = [
  ['run', /run|jog|sprint|treadmill|track/i],
  ['ride', /ride|bike|bicycle|motor|gravel|velomobile|handcycle|recumbent/i],
  ['swim', /swim|pool|open.?water/i],
  ['hike', /hik|walk|trek|climb|scrambl|mountaineer|ruck/i],
  [
    'winter',
    /ski|snow|nordic|snowboard|biathlon|skate|ice.?skate|curling|luge|skeleton|snowshoe/i,
  ],
  [
    'water',
    /row|canoe|kayak|paddle|sail|surf|wind|kite|raft|sup|stand.?up|wakeboard|water.?ski|diving|snorkel|jump/i,
  ],
  [
    'strength',
    /workout|strength|weight|gym|yoga|pilates|cross.?fit|fitnes|core|training|elliptical|stair|indoor/i,
  ],
];

/**
 * Bucket a Strava `sport_type`/`type` into a UI category. Checks the granular
 * `sport_type` first, then the legacy `type`. Mirrors the substring approach
 * of the backend's `matches_sport_type`.
 */
export function sportCategory(
  sportType?: string | null,
  legacyType?: string | null
): SportCategory {
  const candidates = [sportType, legacyType].filter(
    (v): v is string => typeof v === 'string' && v.length > 0
  );
  for (const candidate of candidates) {
    for (const [category, re] of SPORT_RULES) {
      if (re.test(candidate)) return category;
    }
  }
  return 'other';
}

/** Lucide icon name per sport category (curated in lucideIcons.ts). */
export function sportIconName(category: SportCategory | string): string {
  switch (category) {
    case 'run':
      return 'Footprints';
    case 'ride':
      return 'Bike';
    case 'swim':
      return 'Waves';
    case 'hike':
      return 'Mountain';
    case 'winter':
      return 'Snowflake';
    case 'water':
      return 'Sailboat';
    case 'strength':
      return 'Dumbbell';
    default:
      return 'Activity';
  }
}

/** i18n key suffix under `strava.sports.*` for a category. */
export function sportCategoryKey(category: SportCategory | string): string {
  return `sports.${category}`;
}

// ---------------------------------------------------------------------------
// Aggregation (weekly / monthly summaries from fetched activities)
// ---------------------------------------------------------------------------

export interface PeriodTotals {
  count: number;
  distance: number; // meters
  movingTime: number; // seconds
  elapsedTime: number; // seconds
  elevationGain: number; // meters
  calories: number;
}

export const EMPTY_TOTALS: PeriodTotals = {
  count: 0,
  distance: 0,
  movingTime: 0,
  elapsedTime: 0,
  elevationGain: 0,
  calories: 0,
};

function addInto(acc: PeriodTotals, a: StravaActivity): void {
  acc.count += 1;
  acc.distance += a.distance ?? 0;
  acc.movingTime += a.moving_time ?? 0;
  acc.elapsedTime += a.elapsed_time ?? 0;
  acc.elevationGain += a.total_elevation_gain ?? 0;
  acc.calories += a.calories ?? 0;
}

/** ISO-8601 week key "2026-W06" for an ISO date string. */
export function isoWeekKey(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  // ISO week: Thursday of the current week determines the year.
  const date = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const day = date.getUTCDay() || 7; // Mon=1..Sun=7
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return `${date.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

/** Calendar month key "2026-03" for an ISO date string. */
export function monthKey(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

export interface ActivitySummary {
  /** Current ISO week totals (Mon–Sun, UTC). */
  thisWeek: PeriodTotals;
  /** Current calendar month totals (UTC). */
  thisMonth: PeriodTotals;
  /** Per-ISO-week totals, newest first — for a small weekly bar list. */
  byWeek: { key: string; totals: PeriodTotals }[];
  /** Per-month totals, newest first. */
  byMonth: { key: string; totals: PeriodTotals }[];
}

/**
 * Aggregate a fetched activity list into week/month summaries. Strava's
 * `/stats` endpoint only exposes recent(4w)/YTD/all-time totals — weekly and
 * monthly figures are computed client-side from the activity window.
 */
export function summarizeActivities(activities: StravaActivity[]): ActivitySummary {
  const currentWeek = isoWeekKey(new Date().toISOString());
  const currentMonth = monthKey(new Date().toISOString());

  const thisWeek: PeriodTotals = { ...EMPTY_TOTALS };
  const thisMonth: PeriodTotals = { ...EMPTY_TOTALS };
  const weeks = new Map<string, PeriodTotals>();
  const months = new Map<string, PeriodTotals>();

  for (const a of activities) {
    const wk = isoWeekKey(a.start_date);
    const mo = monthKey(a.start_date);
    if (wk) {
      if (wk === currentWeek) addInto(thisWeek, a);
      const acc = weeks.get(wk) ?? { ...EMPTY_TOTALS };
      addInto(acc, a);
      weeks.set(wk, acc);
    }
    if (mo) {
      if (mo === currentMonth) addInto(thisMonth, a);
      const acc = months.get(mo) ?? { ...EMPTY_TOTALS };
      addInto(acc, a);
      months.set(mo, acc);
    }
  }

  const byWeek = [...weeks.entries()]
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([key, totals]) => ({ key, totals }));
  const byMonth = [...months.entries()]
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([key, totals]) => ({ key, totals }));

  return { thisWeek, thisMonth, byWeek, byMonth };
}

/** Merge the three sport buckets of a Strava stats payload into one. */
export function mergeSportTotals(
  ...totals: (StravaSportTotals | undefined)[]
): StravaSportTotals {
  const out: StravaSportTotals = { count: 0, distance: 0, moving_time: 0, elevation_gain: 0 };
  for (const t of totals) {
    if (!t) continue;
    out.count = (out.count ?? 0) + (t.count ?? 0);
    out.distance = (out.distance ?? 0) + (t.distance ?? 0);
    out.moving_time = (out.moving_time ?? 0) + (t.moving_time ?? 0);
    out.elevation_gain = (out.elevation_gain ?? 0) + (t.elevation_gain ?? 0);
  }
  return out;
}
