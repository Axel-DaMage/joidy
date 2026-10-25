import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

// Kit 3 no longer reads `svelte.config.js`: the SvelteKit configuration must be
// passed to every `sveltekit()` plugin invocation (vite.config.ts and
// vitest.config.ts both import this object).
export const kitOptions = {
  preprocess: vitePreprocess(),
  adapter: adapter(),
  // Kit 3 no longer generates the $lib alias implicitly; declare it here
  // so existing `$lib/...` imports keep working without a codebase-wide
  // rename to `#lib`.
  alias: {
    $lib: 'src/lib',
  },
  // Disable SvelteKit's automatic service worker registration. In dev the
  // service worker is not bundled, so the auto-registration tries to evaluate
  // a non-functional /service-worker.js and fails with
  // "ServiceWorker script evaluation failed" on every page load; its fetch
  // handler would also intercept API calls and return 503 Offline while the
  // dev backend restarts. Registration is handled manually in +layout.svelte
  // for production builds only (#205).
  serviceWorker: { register: false },
} as const;
