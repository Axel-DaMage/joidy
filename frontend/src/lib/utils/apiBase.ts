// Runtime API base resolution (#1487, #1582). `joidy up` port-fallback can
// move the published API port off the default when it is already taken (it
// tries default..default+5, see find_free_port in scripts/joidy.sh), so the
// SPA must learn the port at RUNTIME — not from VITE_API_URL, which Vite
// bakes into the bundle at image build time. docker-compose.yml injects the
// resolved port into the frontend container as PUBLIC_API_PORT, declared in
// src/env.ts and read via `$app/env/public` (Kit 3 typed env — adapter-node
// resolves it at runtime per request).
//
// Compose always injects PUBLIC_API_PORT, so a port-only heuristic cannot
// express reverse-proxy/TLS deployments (API on another host/subpath, TLS
// termination in front of a plain-HTTP container). PUBLIC_API_URL (#1582)
// is the full-URL escape hatch and takes top precedence when set.
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

/** Parse PUBLIC_API_URL: a well-formed absolute http(s) URL, else undefined. */
function parsePublicApiUrl(url: string | undefined): URL | undefined {
  if (!url) return undefined;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return undefined;
    return parsed;
  } catch {
    return undefined;
  }
}

/**
 * Resolve the API base URL for browser code. Order (#1487, #1582):
 *  1. PUBLIC_API_URL (runtime env, full URL) — reverse-proxy / TLS / custom
 *     host escape hatch. Subpaths are kept (`https://example.com/api`);
 *     trailing slashes, credentials, query and fragment are normalized away.
 *  2. PUBLIC_API_PORT (runtime env) → <page-protocol>//<page-hostname>:<port>.
 *     Using the page hostname instead of the baked `localhost` also fixes LAN
 *     access, which the build-time VITE_API_URL broke.
 *  3. VITE_API_URL (build-time) — keeps `vite dev` behaviour, where it is
 *     substituted live from the dev-server environment.
 *  4. <page-protocol>//<page-hostname>:8000 — same-origin fallback.
 */
export function resolveBrowserApiBase(
  publicApiUrl: string | undefined,
  publicApiPort: string | undefined,
  viteApiUrl: string | undefined,
  location: { protocol: string; hostname: string }
): string {
  const apiUrl = parsePublicApiUrl(publicApiUrl);
  if (apiUrl) {
    return `${apiUrl.origin}${apiUrl.pathname.replace(/\/+$/, '')}`;
  }
  if (publicApiPort && isValidPort(publicApiPort)) {
    // Number() normalizes whitespace/zero-padding (" 8003", "08003") that
    // isValidPort accepts but which would corrupt the URL if interpolated
    // raw (#1582).
    return `${location.protocol}//${location.hostname}:${Number(publicApiPort)}`;
  }
  if (viteApiUrl) return viteApiUrl;
  return `${location.protocol}//${location.hostname}:${DEFAULT_API_PORT}`;
}

/**
 * Derive the live-updates WebSocket URL from a resolved API base. `https`
 * maps to `wss` and a reverse-proxy subpath is preserved
 * (`https://example.com/api` → `wss://example.com/api/ws`) (#1582).
 */
export function wsUrlForApiBase(base: string): string {
  const parsed = new URL(base);
  const wsProto = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
  const prefix = parsed.pathname.replace(/\/+$/, '');
  return `${wsProto}//${parsed.host}${prefix}/ws`;
}

/** Merge extra sources into the named directives of a serialized CSP,
 * preserving directive order, existing values (no duplicates) and any
 * non-listed directives — including the script-src nonce — untouched. */
function mergeCspSources(csp: string, additions: Record<string, string[]>): string {
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
  // Number() normalizes whitespace/zero-padding before interpolation — same
  // fix as resolveBrowserApiBase (#1582).
  const p = Number(port);
  return mergeCspSources(csp, {
    'connect-src': [`http://*:${p}`, `https://*:${p}`, `ws://*:${p}`, `wss://*:${p}`],
    'img-src': [`http://*:${p}`, `https://*:${p}`],
  });
}

/**
 * Augment a serialized CSP with the PUBLIC_API_URL origin (#1582). CSP
 * host-sources only carry scheme://host[:port] — the subpath of
 * `https://example.com/api` is not expressible, and not needed: what must be
 * reachable is the whole origin. `connect-src` also gets the ws(s) twin for
 * the live-updates socket; `img-src` gets the origin for /uploads.
 */
export function augmentCspWithApiUrl(csp: string, url: string | undefined): string {
  const parsed = parsePublicApiUrl(url);
  if (!parsed) return csp;
  const wsOrigin = `${parsed.protocol === 'https:' ? 'wss' : 'ws'}://${parsed.host}`;
  return mergeCspSources(csp, {
    'connect-src': [parsed.origin, wsOrigin],
    'img-src': [parsed.origin],
  });
}
