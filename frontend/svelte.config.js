import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({ port: 3000 }),
    // Disable SvelteKit's automatic service worker registration. In dev the
    // service worker is not bundled, so the auto-registration tries to evaluate
    // a non-functional /service-worker.js and fails with
    // "ServiceWorker script evaluation failed" on every page load; its fetch
    // handler would also intercept API calls and return 503 Offline while the
    // dev backend restarts. Registration is handled manually in +layout.svelte
    // for production builds only (#205).
    serviceWorker: { register: false }
  }
};

export default config;
