import { describe, it, expect, vi, afterEach } from 'vitest';
import { createTimerRegistry } from './timer';

describe('createTimerRegistry', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('runs a registered timeout callback after the delay', () => {
    vi.useFakeTimers();
    const timers = createTimerRegistry();
    const fn = vi.fn();
    timers.timeout(fn, 100);
    expect(timers.size).toBe(1);

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
    // Fired timeouts untrack themselves.
    expect(timers.size).toBe(0);
  });

  it('runs a registered interval callback repeatedly', () => {
    vi.useFakeTimers();
    const timers = createTimerRegistry();
    const fn = vi.fn();
    timers.interval(fn, 50);

    vi.advanceTimersByTime(160);
    expect(fn).toHaveBeenCalledTimes(3);
    expect(timers.size).toBe(1);
  });

  it('clearAll() prevents pending timeout callbacks from firing', () => {
    vi.useFakeTimers();
    const timers = createTimerRegistry();
    const fn = vi.fn();
    timers.timeout(fn, 100);

    timers.clearAll();
    vi.advanceTimersByTime(1000);
    expect(fn).not.toHaveBeenCalled();
    expect(timers.size).toBe(0);
  });

  it('clearAll() stops tracked intervals', () => {
    vi.useFakeTimers();
    const timers = createTimerRegistry();
    const fn = vi.fn();
    timers.interval(fn, 50);

    vi.advanceTimersByTime(120);
    expect(fn).toHaveBeenCalledTimes(2);

    timers.clearAll();
    vi.advanceTimersByTime(1000);
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it('clear(id) stops a single timer and untracks it', () => {
    vi.useFakeTimers();
    const timers = createTimerRegistry();
    const a = vi.fn();
    const b = vi.fn();
    const idA = timers.timeout(a, 100);
    timers.timeout(b, 100);

    timers.clear(idA);
    vi.advanceTimersByTime(1000);
    expect(a).not.toHaveBeenCalled();
    expect(b).toHaveBeenCalledTimes(1);
  });

  it('clear() accepts both timeout and interval ids, and ignores null/undefined', () => {
    vi.useFakeTimers();
    const timers = createTimerRegistry();
    const fn = vi.fn();
    const id = timers.interval(fn, 50);

    timers.clear(null);
    timers.clear(undefined);
    timers.clear(id);

    vi.advanceTimersByTime(1000);
    expect(fn).not.toHaveBeenCalled();
    expect(timers.size).toBe(0);
  });

  it('clearAll() is idempotent and safe to call twice', () => {
    vi.useFakeTimers();
    const timers = createTimerRegistry();
    const fn = vi.fn();
    timers.timeout(fn, 100);
    timers.clearAll();
    expect(() => timers.clearAll()).not.toThrow();
  });
});
