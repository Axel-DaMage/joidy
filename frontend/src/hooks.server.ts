import type { Handle } from '@sveltejs/kit/hooks';
import { augmentCspWithApiPort, augmentCspWithApiUrl } from '$lib/utils/apiBase';

/**
 * HTTP security headers for the frontend (issue #1283, audit F-11).
 *
 * The Content-Security-Policy itself is emitted by SvelteKit's `csp` option
 * (see kit.options.ts), which attaches a per-request nonce to the hydration
 * bootstrap script. This hook adds the headers SvelteKit does not manage,
 * and a conservative fallback CSP for responses that bypass page rendering
 * (e.g. +server endpoints such as /manifest.json).
 */
export const handle: Handle = async ({ event, resolve }) => {
  const response = await resolve(event);

  response.headers.set('X-Content-Type-Options', 'nosniff');
  // X-Frame-Options is the legacy counterpart of CSP frame-ancestors 'none'.
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('Referrer-Policy', 'no-referrer');
  // Geolocation is used client-side by the weather widget; camera/mic unused.
  response.headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=(self)');

  if (!response.headers.has('Content-Security-Policy')) {
    response.headers.set('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'");
  } else {
    // Kit's CSP wildcards are frozen at image build time and only cover the
    // default 8000-8005 fallback span — a custom API_PORT or a full
    // PUBLIC_API_URL origin (reverse proxy / TLS / subpath) is only known at
    // runtime, so patch it into connect-src/img-src here (#1487, #1582).
    const csp = response.headers.get('Content-Security-Policy');
    if (csp) {
      const augmented = augmentCspWithApiPort(
        augmentCspWithApiUrl(csp, process.env.PUBLIC_API_URL),
        process.env.PUBLIC_API_PORT
      );
      response.headers.set('Content-Security-Policy', augmented);
    }
  }

  return response;
};
