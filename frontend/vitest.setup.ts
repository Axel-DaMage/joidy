// Initialize svelte-i18n for component tests. `initI18n()` is normally called
// from the root layout, but component tests render components directly without
// mounting it, so any component using `$t()` would throw "Cannot format a
// message without first setting the initial locale" (#618).
//
// This must be a dynamic import: static `import` statements are hoisted above
// the localStorage polyfill above, and `stores/locale` reads localStorage at
// module-evaluation time via `detectLocale()`.
const { initI18n } = await import('./src/lib/i18n');
initI18n();
