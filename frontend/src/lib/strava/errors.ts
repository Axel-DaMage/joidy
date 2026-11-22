/**
 * Error mapping for the Strava integration (#44).
 *
 * The API client throws `Error("API <METHOD> <path> → <status>: <body>")`;
 * these helpers classify that string so UI code can render the right
 * localized message (reconnect / rate-limit / not-found / upstream).
 */

export type StravaErrorKind = 'auth' | 'rateLimit' | 'notFound' | 'upstream' | 'generic';

/** Extract the HTTP status embedded in an api.ts error message, if any. */
export function httpStatusOf(e: unknown): number | null {
  const msg = e instanceof Error ? e.message : String(e ?? '');
  const m = msg.match(/→\s*(\d{3})\b/);
  return m ? Number(m[1]) : null;
}

/** True when the failure is a provider 401 — the Strava token needs reconnecting. */
export function isStravaAuthError(e: unknown): boolean {
  return httpStatusOf(e) === 401;
}

/** Map an api.ts error to a `strava.errors.*` i18n key suffix. */
export function stravaErrorKind(e: unknown): StravaErrorKind {
  const status = httpStatusOf(e);
  if (status === 401) return 'auth';
  if (status === 429) return 'rateLimit';
  if (status === 404) return 'notFound';
  if (status !== null && status >= 500) return 'upstream';
  return 'generic';
}
