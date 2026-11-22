import type { AnalyticsOverview, GithubActivityPayload } from '$lib/api';

/**
 * Stale-while-revalidate cache for /analytics/overview (#1499).
 *
 * The overview aggregates tens of thousands of XP events server-side, so
 * revisiting the page or switching back to a window already seen should paint
 * instantly from memory while a background request refreshes it. Entries are
 * keyed by window size and considered fresh for `FRESH_MS`; stale entries are
 * still returned (flagged) so the UI never blocks on the network.
 */

export const FRESH_MS = 60_000;

interface Entry {
  at: number;
  data: AnalyticsOverview;
}

const store = new Map<number, Entry>();

// GitHub activity is cached client-side too (the server also caches it): it
// does not depend on the analysis window and is only fetched on demand.
let github: { at: number; data: GithubActivityPayload } | null = null;

export function readOverview(
  days: number,
  now = Date.now()
): { data: AnalyticsOverview; fresh: boolean; at: number } | null {
  const hit = store.get(days);
  return hit ? { data: hit.data, fresh: now - hit.at < FRESH_MS, at: hit.at } : null;
}

export function writeOverview(days: number, data: AnalyticsOverview, now = Date.now()): void {
  store.set(days, { at: now, data });
}

export function clearOverviewCache(): void {
  store.clear();
  github = null;
}

export function readGithub(now = Date.now()): { data: GithubActivityPayload; fresh: boolean } | null {
  return github ? { data: github.data, fresh: now - github.at < FRESH_MS * 5 } : null;
}

export function writeGithub(data: GithubActivityPayload, now = Date.now()): void {
  github = { at: now, data };
}
