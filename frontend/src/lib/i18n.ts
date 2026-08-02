import { init, addMessages, locale as svelteI18nLocale } from 'svelte-i18n';
import { get } from 'svelte/store';
import { locale as localeStore } from '$lib/stores/locale';
import esCommon from '../locales/es/common.json';
import enCommon from '../locales/en/common.json';

export const SUPPORTED_LOCALES = ['es', 'en'] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];
export const DEFAULT_LOCALE: SupportedLocale = 'es';

/**
 * Map a full BCP-47 locale (e.g. "es-CL", "en-US") to one of the supported
 * svelte-i18n locale keys. Falls back to {@link DEFAULT_LOCALE} when no match.
 */
export function mapToSupportedLocale(raw: string): SupportedLocale {
  const base = raw.toLowerCase().split('-')[0];
  if (SUPPORTED_LOCALES.includes(base as SupportedLocale)) {
    return base as SupportedLocale;
  }
  return DEFAULT_LOCALE;
}

let initialized = false;

/**
 * Initialize svelte-i18n with the bundled locale messages and sync it with the
 * existing `stores/locale` store (which handles detection + persistence).
 *
 * Must be called once at app start (e.g. from the root layout). Subsequent
 * calls are no-ops. Changing the locale via `setLocale()` from `stores/locale`
 * automatically propagates to svelte-i18n through the subscription set up here.
 */
export function initI18n(): void {
  if (initialized) return;
  initialized = true;

  addMessages('es', esCommon);
  addMessages('en', enCommon);

  init({
    fallbackLocale: DEFAULT_LOCALE,
    initialLocale: mapToSupportedLocale(get(localeStore)),
  });

  // Keep svelte-i18n's locale in sync with the app locale store. The store
  // holds the full BCP-47 tag (e.g. "es-CL") for Intl date/time formatting,
  // while svelte-i18n only needs the base language key ("es").
  localeStore.subscribe((fullLocale) => {
    svelteI18nLocale.set(mapToSupportedLocale(fullLocale));
  });
}
