import { writable } from 'svelte/store';
import { browser } from '$app/environment';

/**
 * Configurable UI locale (#370).
 *
 * Previously the app hardcoded `'es-CL'` / `'es'` in every date/time/sort call,
 * coupling the UI to a single locale. This store:
 *   - detects the browser language on first load,
 *   - lets the user override it (persisted to localStorage),
 *   - exposes a synchronous `getLocale()` for use in non-reactive `.ts` utils.
 */
const STORAGE_KEY = 'joidy:locale';

function detectLocale(): string {
  if (!browser) return 'es-CL';
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return saved;
  } catch {
    /* localStorage unavailable (private mode) — fall through */
  }
  // Default to 'es-CL' since the UI is primarily in Spanish (#560).
  // Browser language detection is intentionally disabled until the i18n
  // migration (#572) is complete — otherwise the combobox shows "English"
  // while the UI remains in Spanish, which is confusing.
  return 'es-CL';
}

export const locale = writable<string>(detectLocale());

export function setLocale(value: string): void {
  locale.set(value);
  if (browser) {
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch {
      /* ignore persistence errors */
    }
  }
}

/** Synchronous accessor for use in non-reactive `.ts` utilities. */
export function getLocale(): string {
  let value = detectLocale();
  const unsub = locale.subscribe(v => (value = v));
  unsub();
  return value;
}
