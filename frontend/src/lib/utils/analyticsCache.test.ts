import { beforeEach, describe, expect, it } from 'vitest';
import { FRESH_MS, clearOverviewCache, readOverview, writeOverview } from './analyticsCache';
import type { AnalyticsOverview } from '$lib/api';

const payload = { days: 90 } as AnalyticsOverview;

describe('analytics overview cache', () => {
  beforeEach(() => clearOverviewCache());

  it('misses when nothing was stored for that window', () => {
    expect(readOverview(90)).toBeNull();
  });

  it('returns fresh data inside the TTL and flags it stale afterwards', () => {
    writeOverview(90, payload, 1_000);
    expect(readOverview(90, 1_000 + FRESH_MS - 1)?.fresh).toBe(true);
    const stale = readOverview(90, 1_000 + FRESH_MS + 1);
    expect(stale?.fresh).toBe(false);
    expect(stale?.data).toBe(payload);
  });

  it('keeps windows independent', () => {
    writeOverview(90, payload);
    expect(readOverview(180)).toBeNull();
  });
});
