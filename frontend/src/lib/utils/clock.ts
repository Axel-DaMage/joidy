import { browser } from '$app/environment';
import { getLocale } from '$lib/stores/locale';

const TZ_KEY = 'joidy-timezone';

/**
 * Read the user's selected timezone from localStorage (same key used by
 * TimeWidget). Falls back to the browser's detected timezone, then UTC.
 */
export function getTimezone(): string {
  if (!browser) return 'UTC';
  try {
    const saved = localStorage.getItem(TZ_KEY);
    if (saved) return saved;
  } catch {
    /* localStorage unavailable (private mode) — fall through */
  }
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

/**
 * Today's date key (YYYY-MM-DD) in the given timezone.
 *
 * `toISOString()` returns the *UTC* date, which drifts one day off the
 * user's local date near midnight — daily notes, streaks and check-ins
 * (#864, #1099) must use this instead.
 * Returns '1970-01-01' if the timezone is invalid (same guard style as the
 * other helpers).
 */
export function getTodayKey(tz: string = getTimezone(), date: Date = new Date()): string {
  try {
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: tz,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(date);
  } catch {
    return '1970-01-01';
  }
}

/**
 * Format the current time for a timezone, honoring the 24h/12h preference.
 * Returns `--:--:--` if the timezone is invalid (mirrors TimeWidget's guard).
 */
export function formatClock(tz: string, use24h: boolean, locale: string = getLocale()): string {
  try {
    return new Date().toLocaleTimeString(locale, {
      timeZone: tz,
      hour: use24h ? '2-digit' : 'numeric',
      minute: '2-digit',
      second: '2-digit',
      hour12: !use24h,
    });
  } catch {
    return '--:--:--';
  }
}

// ── Clock styles (#707) ──────────────────────────────────────────────────────

/** Selectable visual styles for clocks and timers across the app. */
export const CLOCK_STYLES = [
  'digital',
  'circular',
  'material',
  'minimalist',
  'flip',
  'binary',
] as const;

export type ClockStyleId = (typeof CLOCK_STYLES)[number];

export const DEFAULT_CLOCK_STYLE: ClockStyleId = 'digital';

export function isClockStyleId(value: unknown): value is ClockStyleId {
  return typeof value === 'string' && (CLOCK_STYLES as readonly string[]).includes(value);
}

/**
 * Structured time parts consumed by the clock-style components. The formatted
 * strings honor the locale and 12h/24h preference; the numeric fields drive
 * visualizations that need raw values (analog hands, binary digits).
 */
export interface ClockParts {
  hours: string;
  minutes: string;
  seconds: string;
  ampm: string | null;
  h: number;
  m: number;
  s: number;
}

const EMPTY_PARTS: ClockParts = {
  hours: '--',
  minutes: '--',
  seconds: '--',
  ampm: null,
  h: 0,
  m: 0,
  s: 0,
};

/**
 * Split the current time for a timezone into display parts, honoring the
 * 12h/24h preference. Returns `--` placeholders for invalid timezones.
 */
export function getClockParts(
  tz: string,
  use24h: boolean,
  locale: string = getLocale(),
  date: Date = new Date()
): ClockParts {
  try {
    const raw = new Intl.DateTimeFormat(locale, {
      timeZone: tz,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: !use24h,
    }).formatToParts(date);
    const pick = (type: Intl.DateTimeFormatPartTypes): string =>
      raw.find((p) => p.type === type)?.value ?? '--';
    const ampmRaw = pick('dayPeriod');
    return {
      hours: pick('hour'),
      minutes: pick('minute'),
      seconds: pick('second'),
      ampm: ampmRaw === '--' ? null : ampmRaw,
      h: parseInt(pick('hour'), 10) || 0,
      m: parseInt(pick('minute'), 10) || 0,
      s: parseInt(pick('second'), 10) || 0,
    };
  } catch {
    return { ...EMPTY_PARTS };
  }
}

/**
 * Split a remaining-seconds countdown into display parts for timer mode.
 * Hours stay at 0 for sub-hour countdowns — style components decide whether
 * to render the hour segment.
 */
export function getTimerParts(secondsLeft: number): ClockParts {
  const total = Math.max(0, Math.floor(secondsLeft));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  return {
    hours: pad(h),
    minutes: pad(m),
    seconds: pad(s),
    ampm: null,
    h,
    m,
    s,
  };
}
