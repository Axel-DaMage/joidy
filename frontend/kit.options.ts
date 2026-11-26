import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import type { Config } from '@sveltejs/kit/vite';
import { API_PORT_RANGE } from './src/lib/utils/apiBase';

// Kit 3 no longer reads `svelte.config.js`: the SvelteKit configuration must be
// passed to every `sveltekit()` plugin invocation (vite.config.ts and
// vitest.config.ts both import this object).

// ── CSP sources for the API origin (#1283) ────────────────────────────────────
// The browser resolves the API base at runtime (PUBLIC_API_URL →
// PUBLIC_API_PORT → VITE_API_URL → <page-host>:8000 — see
// src/lib/utils/apiBase.ts, #1487/#1582). `joidy up`
// port-fallback can move the published API port anywhere inside
// default..default+5, so the `*:<port>` host-wildcard sources must cover the
// whole API_PORT_RANGE (8000-8005 by default), not just :8000.
type CspSource = NonNullable<
  NonNullable<NonNullable<Config['csp']>['directives']>['connect-src']
>[number];

// Kit's Csp.Source literal union requires a dotted hostname or 'localhost';
// `*`-host sources are spec-valid CSP host-sources but outside that literal
// type, and parsed origins are plain strings at runtime — this helper
// bridges both without touching the rest of the (fully checked) directives.
const src = (s: string): CspSource => s as unknown as CspSource;

const apiConnectSources = new Set<CspSource>();
const apiImageSources: CspSource[] = [];
for (const port of API_PORT_RANGE) {
  apiConnectSources.add(src(`http://*:${port}`));
  apiConnectSources.add(src(`https://*:${port}`));
  apiConnectSources.add(src(`ws://*:${port}`));
  apiConnectSources.add(src(`wss://*:${port}`));
  apiImageSources.push(src(`http://*:${port}`), src(`https://*:${port}`));
}

const apiUrl = process.env.VITE_API_URL;
if (apiUrl) {
  try {
    const parsed = new URL(apiUrl);
    apiConnectSources.add(src(parsed.origin));
    // The live-updates WebSocket uses the same host/port over ws(s).
    apiConnectSources.add(src(`${parsed.protocol === 'https:' ? 'wss' : 'ws'}://${parsed.host}`));
  } catch {
    // Malformed VITE_API_URL — the port-range wildcards still cover the fallback.
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
  // Emit .gz/.br alongside the static output so the production node server
  // can serve precompressed assets (#1311).
  adapter: adapter({ precompress: true }),
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
      // The sha256 pins the anti-FOUC theme bootstrap in app.html — it must
      // be regenerated (sha256 of the exact <script> body) whenever that
      // inline script changes.
      'script-src': ['self', src('sha256-SwCUq3cit6aT8FrR7jN/j+zlKIVx9C9o+J5wWtnAzh0=')],
      // Svelte component styles, TipTap marks and rendered markdown all
      // rely on style attributes; dev adds 'unsafe-inline' anyway.
      'style-src': ['self', 'unsafe-inline'],
      // /uploads images are served by the API origin (any port inside the
      // fallback range, #1487); data:/blob: cover TipTap previews and
      // generated share images.
      'img-src': ['self', 'data:', 'blob:', ...apiImageSources],
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
