// Namespaced localStorage helpers for view-level UI preferences (#1673).
//
// Keys follow the `joidy.<view>.<prop>` convention; values are JSON-encoded so
// any JSON-safe type round-trips losslessly. Every read/write is SSR-guarded
// (`browser`) and wrapped in try/catch — storage can throw (private mode,
// quota, disabled storage) and a broken pref must degrade to the caller's
// default, never crash the view.
//
// The `joidy.` dotted prefix is intentionally NOT in `USER_DATA_KEYS` /
// `USER_DATA_PREFIXES` (see `$lib/stores/session.ts`): these keys hold
// device-level view preferences — tab, sort, filters, collapsed panels —
// that must survive logout, unlike user data (drafts, caches, note content)
// which is purged. Keep user-typed content (search text, note content,
// vault paths) out of this namespace and in `user_settings` instead; a bare
// entity id used only as selection state (e.g. the last-opened goal) is OK.
import { browser } from '$app/env';

/** Shared prefix for every view-preference key (`joidy.<view>.<prop>`). */
export const VIEW_PREF_PREFIX = 'joidy.';

export function prefKey(view: string, prop: string): string {
  return `${VIEW_PREF_PREFIX}${view}.${prop}`;
}

export interface LoadPrefOptions<T> {
  /**
   * Legacy storage key to migrate from when the namespaced key is absent.
   * Legacy values were stored as raw strings (not JSON); `legacyFrom`
   * converts them — otherwise the raw string is JSON-parsed when possible
   * and used verbatim when not. On a successful read the value is rewritten
   * under the namespaced key and the legacy key is removed.
   */
  legacyKey?: string;
  /** Converts a raw legacy string into the typed value. */
  // eslint-disable-next-line no-unused-vars -- type-position param name is documentation
  legacyFrom?: (raw: string) => T;
  /** Optional validator — a value that fails it falls back to `fallback`. */
  // eslint-disable-next-line no-unused-vars -- type-position param name is documentation
  isValid?: (value: unknown) => boolean;
}

function migrateLegacyValue<T>(raw: string): T {
  try {
    return JSON.parse(raw) as T;
  } catch {
    // Legacy ad-hoc keys stored bare strings (e.g. 'editor', 'month').
    return raw as T;
  }
}

/**
 * Reads a view preference from localStorage. Returns `fallback` when the key
 * is absent, unparseable, rejected by `isValid`, or storage is unavailable.
 */
export function loadPref<T>(
  view: string,
  prop: string,
  fallback: T,
  opts: LoadPrefOptions<T> = {}
): T {
  if (!browser) return fallback;
  try {
    const raw = localStorage.getItem(prefKey(view, prop));
    if (raw !== null) {
      const parsed = JSON.parse(raw) as unknown;
      if (opts.isValid && !opts.isValid(parsed)) return fallback;
      return parsed as T;
    }
    if (opts.legacyKey) {
      const legacy = localStorage.getItem(opts.legacyKey);
      if (legacy !== null) {
        const value = opts.legacyFrom ? opts.legacyFrom(legacy) : migrateLegacyValue<T>(legacy);
        localStorage.removeItem(opts.legacyKey);
        if (opts.isValid && !opts.isValid(value)) return fallback;
        savePref(view, prop, value);
        return value;
      }
    }
  } catch {
    return fallback;
  }
  return fallback;
}

/**
 * Writes a view preference to localStorage. `undefined` removes the key —
 * there is no meaningful JSON representation for it. Write failures
 * (quota, private mode) are swallowed: prefs are best-effort by design.
 */
export function savePref<T>(view: string, prop: string, value: T): void {
  if (!browser) return;
  try {
    if (value === undefined) {
      localStorage.removeItem(prefKey(view, prop));
      return;
    }
    localStorage.setItem(prefKey(view, prop), JSON.stringify(value));
  } catch {
    /* best-effort persistence */
  }
}

export function removePref(view: string, prop: string): void {
  if (!browser) return;
  try {
    localStorage.removeItem(prefKey(view, prop));
  } catch {
    /* best-effort cleanup */
  }
}
