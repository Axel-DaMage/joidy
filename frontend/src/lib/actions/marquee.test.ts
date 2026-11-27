import { describe, it, expect } from 'vitest';
import {
  buildMarqueeKeyframes,
  computeMarqueeTiming,
  parseDwellSeconds,
} from './marquee';

// SPEED_PX_PER_S = 32, MIN_SCROLL_S = 2, DEFAULT_DWELL_S = 1 (marquee.ts).

describe('computeMarqueeTiming', () => {
  it('adds the dwell on top of a constant-speed scroll segment', () => {
    // 320px at 32px/s → 10s scroll + 1s dwell.
    const t = computeMarqueeTiming(320, 1);
    expect(t.scrollSeconds).toBe(10);
    expect(t.durationMs).toBe(11000);
    expect(t.dwellFraction).toBeCloseTo(1 / 11, 6);
  });

  it('keeps the dwell an absolute time regardless of title length', () => {
    // 96px → 3s scroll; the same 1s dwell is a larger cycle share.
    const t = computeMarqueeTiming(96, 1);
    expect(t.durationMs).toBe(4000);
    expect(t.dwellFraction).toBeCloseTo(0.25, 6);
  });

  it('clamps the scroll segment to the minimum duration', () => {
    const t = computeMarqueeTiming(0, 1);
    expect(t.scrollSeconds).toBe(2);
    expect(t.durationMs).toBe(3000);
    expect(t.dwellFraction).toBeCloseTo(1 / 3, 6);
  });

  it('degenerates to a pure scroll loop when the dwell is zero', () => {
    const t = computeMarqueeTiming(320, 0);
    expect(t.durationMs).toBe(10000);
    expect(t.dwellFraction).toBe(0);
  });

  it('treats a negative dwell as zero', () => {
    const t = computeMarqueeTiming(320, -5);
    expect(t.durationMs).toBe(10000);
    expect(t.dwellFraction).toBe(0);
  });
});

describe('buildMarqueeKeyframes', () => {
  it('holds the title start for the dwell, then scrolls one copy width', () => {
    const frames = buildMarqueeKeyframes(computeMarqueeTiming(320, 1));
    expect(frames).toHaveLength(3);
    expect(frames[0]).toEqual({ transform: 'translateX(0)', offset: 0 });
    // Hold ends at the dwell fraction — title start stays visible ~1s.
    expect(frames[1].transform).toBe('translateX(0)');
    expect(frames[1].offset).toBeCloseTo(1 / 11, 6);
    // -50% is visually identical to 0 (second copy) → seamless wrap.
    expect(frames[2]).toEqual({ transform: 'translateX(-50%)', offset: 1 });
  });

  it('produces monotonically non-decreasing offsets', () => {
    const frames = buildMarqueeKeyframes(computeMarqueeTiming(64, 0));
    const offsets = frames.map((f) => f.offset ?? 0);
    expect(offsets).toEqual([...offsets].sort((a, b) => a - b));
  });
});

describe('parseDwellSeconds', () => {
  it('parses seconds, milliseconds, and unitless values', () => {
    expect(parseDwellSeconds('1s')).toBe(1);
    expect(parseDwellSeconds('1.5s')).toBe(1.5);
    expect(parseDwellSeconds('250ms')).toBe(0.25);
    expect(parseDwellSeconds(' 500MS ')).toBe(0.5);
    expect(parseDwellSeconds('2')).toBe(2);
    expect(parseDwellSeconds('0s')).toBe(0);
  });

  it('falls back to the 1s default on missing or invalid input', () => {
    expect(parseDwellSeconds(undefined)).toBe(1);
    expect(parseDwellSeconds(null)).toBe(1);
    expect(parseDwellSeconds('')).toBe(1);
    expect(parseDwellSeconds('abc')).toBe(1);
    expect(parseDwellSeconds('-1s')).toBe(1);
  });
});
