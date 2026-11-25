// Runtime API base resolution (#1487). `joidy up` port-fallback can move the
// published API port off the default when it is already taken (it tries
// default..default+5, see find_free_port in scripts/joidy.sh), so the SPA
// must learn the port at RUNTIME — not from VITE_API_URL, which Vite bakes
// into the bundle at image build time. docker-compose.yml injects the
// resolved port into the frontend container as PUBLIC_API_PORT, declared in
// src/env.ts and read via `$app/env/public` (Kit 3 typed env — adapter-node
// resolves it at runtime per request).
//
// This module is intentionally free of SvelteKit imports so the service
// worker and kit.options.ts can share the constants.

/** API host port used when nothing is configured. */
export const DEFAULT_API_PORT = 8000;

/** Port-fallback span: `joidy up` tries start..start+SPAN (6 ports). */
export const API_PORT_FALLBACK_SPAN = 5;

/** Inclusive [base, base+SPAN] port range an API call may land on. */
export const API_PORT_RANGE = Array.from(
  { length: API_PORT_FALLBACK_SPAN + 1 },
  (_, i) => DEFAULT_API_PORT + i
);

function isValidPort(port: string): boolean {
  const n = Number(port);
  return Number.isInteger(n) && n >= 1 && n <= 65535;
}

/**
 * Resolve the API base URL for browser code. Order (#1487):
 *  1. PUBLIC_API_PORT (runtime env) → <page-protocol>//<page-hostname>:<port>.
 *     Using the page hostname instead of the baked `localhost` also fixes LAN
 *     access, which the build-time VITE_API_URL broke.
 *  2. VITE_API_URL (build-time) — keeps `vite dev` behaviour, where it is
 *     substituted live from the dev-server environment.
 *  3. <page-protocol>//<page-hostname>:8000 — same-origin fallback.
 */
export function resolveBrowserApiBase(
  publicApiPort: string | undefined,
  viteApiUrl: string | undefined,
  location: { protocol: string; hostname: string }
): string {
  if (publicApiPort && isValidPort(publicApiPort)) {
    return `${location.protocol}//${location.hostname}:${publicApiPort}`;
  }
  if (viteApiUrl) return viteApiUrl;
  return `${location.protocol}//${location.hostname}:${DEFAULT_API_PORT}`;
}

/**
 * Augment a serialized Content-Security-Policy with the runtime API port
 * (#1487). The static `*:<port>` wildcards in kit.options.ts only cover the
 * default fallback range (8000-8005) because they are frozen at image build
 * time — a custom `API_PORT` (e.g. 9000, scanned 9000-9005 by `joidy up`)
 * would still be blocked. The server process knows the real port at runtime
 * via PUBLIC_API_PORT, so hooks.server.ts patches it into `connect-src`
 * (REST + WebSocket) and `img-src` (/uploads) per response. Directives not
 * listed here — including the script-src nonce — pass through untouched.
 */
export function augmentCspWithApiPort(csp: string, port: string | undefined): string {
  if (!port || !isValidPort(port)) return csp;
  const additions: Record<string, string[]> = {
    'connect-src': [`http://*:${port}`, `https://*:${port}`, `ws://*:${port}`, `wss://*:${port}`],
    'img-src': [`http://*:${port}`, `https://*:${port}`],
  };
  return csp
    .split(';')
    .map((directive) => {
      const trimmed = directive.trim();
      if (!trimmed) return trimmed;
      const [name, ...values] = trimmed.split(/\s+/);
      const extra = additions[name];
      if (!extra) return trimmed;
      const merged = [...values, ...extra.filter((s) => !values.includes(s))];
      return `${name} ${merged.join(' ')}`;
    })
    .join('; ');
}
