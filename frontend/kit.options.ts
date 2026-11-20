import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import type { Config } from '@sveltejs/kit/vite';

// Kit 3 no longer reads `svelte.config.js`: the SvelteKit configuration must be
// passed to every `sveltekit()` plugin invocation (vite.config.ts and
// vitest.config.ts both import this object).

// ── CSP sources for the API origin (#1283) ────────────────────────────────────
// The browser talks to the API on VITE_API_URL when set (baked by the
// Dockerfile build ARG / compose env) and falls back to <page-host>:8000
// otherwise — see src/lib/api.ts and the WebSocket code in +layout.svelte.
// The `*:8000` host-wildcard sources cover the fallback case on any host.
type CspSource = NonNullable<
  NonNullable<NonNullable<Config['csp']>['directives']>['connect-src']
>[number];

// Kit's Csp.Source literal union requires a dotted hostname or 'localhost';
// `*`-host sources are spec-valid CSP host-sources but outside that literal
// type, and parsed origins are plain strings at runtime — this helper
// bridges both without touching the rest of the (fully checked) directives.
const src = (s: string): CspSource => s as unknown as CspSource;

const apiConnectSources = new Set<CspSource>([
  src('http://*:8000'),
  src('https://*:8000'),
  src('ws://*:8000'),
  src('wss://*:8000'),
]);

const apiUrl = process.env.VITE_API_URL;
if (apiUrl) {
  try {
    const parsed = new URL(apiUrl);
    apiConnectSources.add(src(parsed.origin));
    // The live-updates WebSocket uses the same host/port over ws(s).
    apiConnectSources.add(src(`${parsed.protocol === 'https:' ? 'wss' : 'ws'}://${parsed.host}`));
  } catch {
    // Malformed VITE_API_URL — the :8000 wildcards still cover the fallback.
  }
}

// Vite dev HMR opens a WebSocket to JOIDY_HMR_HOST (default 127.0.0.1, see
// vite.config.ts) which may differ from the page host (localhost / LAN IP).
if (process.env.NODE_ENV !== 'production') {
  apiConnectSources.add('ws://127.0.0.1:*');
  apiConnectSources.add('ws://localhost:*');
}

export const kitOptions: Config = {
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
  // HTTP Content-Security-Policy (#1283, audit F-11). Emitted by SvelteKit
  // itself so the hydration bootstrap script gets a per-request nonce (or a
  // sha256 hash for prerendered pages) — keeping script-src free of
  // 'unsafe-inline'/'unsafe-eval'. The remaining security headers
  // (nosniff, X-Frame-Options, Referrer-Policy) live in src/hooks.server.ts.
  csp: {
    // `as const` keeps the literal type ('auto' | 'hash' | 'nonce') that the
    // SvelteKit Config type requires.
    mode: 'auto' as const,
    directives: {
      'default-src': ['self'],
      // Kit injects nonce-<v>/sha256-<v> for its inline bootstrap script.
      // No 'unsafe-eval': the calculator's `new Function` sink was removed
      // in favor of a safe parser (src/lib/utils/mathEval.ts, audit F-10).
      'script-src': ['self'],
      // Svelte component styles, TipTap marks and rendered markdown all
      // rely on style attributes; dev adds 'unsafe-inline' anyway.
      'style-src': ['self', 'unsafe-inline'],
      // /uploads images are served by the API origin (:8000); data:/blob:
      // cover TipTap previews and generated share images.
      'img-src': ['self', 'data:', 'blob:', src('http://*:8000'), src('https://*:8000')],
      // Self-hosted Geist fonts in static/fonts.
      'font-src': ['self'],
      // 'self' (same-origin fetches + service worker) + the API origin +
      // api.open-meteo.com (weather widget) + data: (html-to-image).
      'connect-src': ['self', 'data:', 'https://api.open-meteo.com', ...apiConnectSources],
      'worker-src': ['self', 'blob:'],
      'manifest-src': ['self'],
      'object-src': ['none'],
      'frame-src': ['none'],
      'base-uri': ['self'],
      'form-action': ['self'],
      'frame-ancestors': ['none'],
    },
  },
};
