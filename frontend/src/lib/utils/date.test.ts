import { describe, it, expect, vi } from 'vitest';

vi.mock('$app/env', () => ({ browser: true, dev: false }));

import { localDayKey, parseLocalDate } from './date';

describe('parseLocalDate (#1306)', () => {
  it('parses a date-only string as a local date, not UTC midnight', () => {
    const d = parseLocalDate('2026-01-15');
    // `new Date('2026-01-15')` is UTC midnight — in UTC−N zones .getDate()
    // returns 14. The local parse must always yield the literal day.
    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(0);
    expect(d.getDate()).toBe(15);
  });

  it('anchors at local noon so DST edges cannot shift the day', () => {
    expect(parseLocalDate('2026-01-15').getHours()).toBe(12);
    expect(localDayKey(parseLocalDate('2026-03-08'))).toBe('2026-03-08');
  });

  it('pads and preserves single-digit months/days', () => {
    const d = parseLocalDate('2026-02-03');
    expect(d.getMonth()).toBe(1);
    expect(d.getDate()).toBe(3);
  });

  it('passes full datetimes through to new Date', () => {
    const iso = '2026-01-15T14:30:00Z';
    expect(parseLocalDate(iso).getTime()).toBe(new Date(iso).getTime());
  });
});

describe('localDayKey (#1306)', () => {
  it('returns the local YYYY-MM-DD key, never the UTC day', () => {
    // 2026-01-15T23:30 local is still Jan 15 locally even when it is already
    // Jan 16 in UTC (any positive-offset zone) — the key must be local.
    const d = new Date(2026, 0, 15, 23, 30);
    expect(localDayKey(d)).toBe('2026-01-15');
  });

  it('zero-pads month and day', () => {
    expect(localDayKey(new Date(2026, 1, 3))).toBe('2026-02-03');
  });
});
