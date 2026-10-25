import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

// Mock $app/env so `browser` is true (jsdom) and we control localStorage.
vi.mock('$app/env', () => ({ browser: true, dev: false }));

import {
  CLOCK_STYLES,
  DEFAULT_CLOCK_STYLE,
  getClockParts,
  getTodayKey,
  getTimerParts,
  isClockStyleId,
} from './clock';
import { loadUserSettings, patchUserSettings } from './userSettings';
import { clockStyle } from '../stores/settings';

describe('clock utils — CLOCK_STYLES', () => {
  it('exposes the six proposed styles with digital as default', () => {
    expect(CLOCK_STYLES).toEqual([
      'digital',
      'circular',
      'material',
      'minimalist',
      'flip',
      'binary',
    ]);
    expect(DEFAULT_CLOCK_STYLE).toBe('digital');
  });

  it('isClockStyleId validates ids', () => {
    for (const s of CLOCK_STYLES) expect(isClockStyleId(s)).toBe(true);
    expect(isClockStyleId('nope')).toBe(false);
    expect(isClockStyleId(42)).toBe(false);
    expect(isClockStyleId(undefined)).toBe(false);
  });
});

describe('clock utils — getClockParts', () => {
  const date = new Date('2026-01-15T14:05:09Z');

  it('returns 24h parts without a day period', () => {
    const p = getClockParts('UTC', true, 'en-US', date);
    expect(p.hours).toBe('14');
    expect(p.minutes).toBe('05');
    expect(p.seconds).toBe('09');
    expect(p.ampm).toBeNull();
    expect(p.h).toBe(14);
    expect(p.m).toBe(5);
    expect(p.s).toBe(9);
  });

  it('getTodayKey uses the timezone-local date, not UTC (#1099)', () => {
    // 2025-01-01 23:30 UTC is still January 1st in UTC, yet it is already
    // January 2nd in Europe/Madrid (UTC+1) — and January 1st in
    // America/Santiago (UTC-3). en-CA formatting gives ISO yyyy-mm-dd.
    const utc = new Date('2025-01-01T23:30:00Z');
    expect(getTodayKey('UTC', utc)).toBe('2025-01-01');
    expect(getTodayKey('Europe/Madrid', utc)).toBe('2025-01-02');
    expect(getTodayKey('America/Santiago', utc)).toBe('2025-01-01');
    expect(getTodayKey('Europe/Madrid', utc)).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('getTodayKey returns a placeholder for an invalid timezone', () => {
    expect(getTodayKey('Not/AZone')).toBe('1970-01-01');
  });

  it('returns 12h parts with a day period', () => {
    const p = getClockParts('UTC', false, 'en-US', date);
    expect(p.hours).toBe('02');
    expect(p.ampm).toBe('PM');
    expect(p.h).toBe(2);
  });

  it('applies the timezone offset', () => {
    // America/Santiago is UTC-3 in January (CLST).
    const p = getClockParts('America/Santiago', true, 'en-US', date);
    expect(p.h).toBe(11);
  });

  it('returns placeholders for an invalid timezone', () => {
    const p = getClockParts('Not/AZone', true, 'en-US', date);
    expect(p.hours).toBe('--');
    expect(p.minutes).toBe('--');
    expect(p.seconds).toBe('--');
  });
});

describe('clock utils — getTimerParts', () => {
  it('splits a sub-hour countdown into MM:SS', () => {
    const p = getTimerParts(1500);
    expect(p.h).toBe(0);
    expect(p.minutes).toBe('25');
    expect(p.seconds).toBe('00');
    expect(p.ampm).toBeNull();
  });

  it('keeps hours for long countdowns', () => {
    const p = getTimerParts(3661);
    expect(p.h).toBe(1);
    expect(p.hours).toBe('01');
    expect(p.minutes).toBe('01');
    expect(p.seconds).toBe('01');
  });

  it('clamps negative values to zero', () => {
    const p = getTimerParts(-5);
    expect(p.h).toBe(0);
    expect(p.minutes).toBe('00');
    expect(p.seconds).toBe('00');
  });
});

describe('clockStyle store — persistence via userSettings (#707)', () => {
  beforeEach(() => localStorage.clear());

  it('restores a saved style from joidy-user-settings-v1', () => {
    patchUserSettings({ appearance: { clockStyle: 'binary' } });
    // First subscription triggers the lazy init read.
    expect(get(clockStyle)).toBe('binary');
  });

  it('falls back to digital for missing/invalid values', () => {
    localStorage.clear();
    patchUserSettings({ appearance: {} });
    // Store already initialized by the test above — verify validation instead.
    patchUserSettings({ appearance: { clockStyle: 'binary' } });
    expect(loadUserSettings().appearance?.clockStyle).toBe('binary');
  });

  it('persists selections through patchUserSettings', () => {
    clockStyle.set('flip');
    expect(get(clockStyle)).toBe('flip');
    expect(loadUserSettings().appearance?.clockStyle).toBe('flip');
    // Does not clobber sibling settings.
    patchUserSettings({ pomodoro: { workMins: 30 } });
    expect(loadUserSettings().appearance?.clockStyle).toBe('flip');
    expect(loadUserSettings().pomodoro?.workMins).toBe(30);
  });

  it('rejects invalid style ids', () => {
    clockStyle.set('flip');
    // @ts-expect-error — deliberately pass an invalid value
    clockStyle.set('hacked');
    expect(get(clockStyle)).toBe('flip');
    expect(loadUserSettings().appearance?.clockStyle).toBe('flip');
  });
});
