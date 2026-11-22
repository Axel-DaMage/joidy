import type { AnalyticsOverview } from '$lib/api';

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
}
