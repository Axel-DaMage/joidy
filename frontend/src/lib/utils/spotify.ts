// Spotify frontend helpers (#45).
//
// - Manual access-token override: the backend honors an `X-Spotify-Token`
//   header on every data endpoint (stored OAuth token remains the default).
//   Self-hosters without a Spotify OAuth app can paste a token here; it is
//   kept in localStorage only — never sent anywhere but the Joidy API.
// - Error-status extraction: `req()` attaches `.status` to thrown errors;
//   the regex fallback keeps this working if an older error shape slips by.
// - Small display formatters shared by the /spotify page, its sections and
//   the dashboard widget.

import { browser } from '$app/env';

const TOKEN_KEY = 'joidy_spotify_token';

export function getSpotifyTokenOverride(): string {
  if (!browser) return '';
  try {
    return localStorage.getItem(TOKEN_KEY)?.trim() ?? '';
  } catch {
    return '';
  }
}

export function setSpotifyTokenOverride(token: string): void {
  if (!browser) return;
  try {
    const trimmed = token.trim();
    if (trimmed) {
      localStorage.setItem(TOKEN_KEY, trimmed);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // Storage unavailable (private mode / quota) — the override just won't
    // persist; callers still get the in-memory value for this session.
  }
}

export function clearSpotifyTokenOverride(): void {
  setSpotifyTokenOverride('');
}

/** HTTP status of a failed `api.spotify.*` call, or null when unknown. */
export function spotifyErrorStatus(err: unknown): number | null {
  const status = (err as { status?: unknown } | null)?.status;
  if (typeof status === 'number') return status;
  const match = /→ (\d{3}):/.exec((err as Error | null)?.message ?? '');
  return match ? Number(match[1]) : null;
}

/** `duration_ms` → `m:ss` (or `h:mm:ss` past one hour). */
export function formatDuration(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms) || ms < 0) return '0:00';
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const ss = String(s).padStart(2, '0');
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`;
}

/** ISO timestamp → short localized date+time ("12 mar, 21:04"). */
export function formatPlayedAt(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}
