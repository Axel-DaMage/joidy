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
 * Format the current time for a timezone, honoring the 24h/12h preference.
 * Returns `--:--:--` if the timezone is invalid (mirrors TimeWidget's guard).
 */
export function formatClock(
  tz: string,
  use24h: boolean,
  locale: string = getLocale(),
): string {
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
