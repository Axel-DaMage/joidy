import type { Handle } from '@sveltejs/kit/hooks';

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
  }

  return response;
};
