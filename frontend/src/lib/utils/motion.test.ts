import { describe, it, expect, vi, afterEach } from 'vitest';
import {
  MOTION_DURATION,
  backdropIn,
  dialogIn,
  drawerIn,
  enter,
  growX,
  popIn,
  prefersReducedMotion,
  rise,
  staggerDelay,
  staggerStyle,
  tweenNumber,
} from './motion';

const node = document.createElement('div');

function stubReducedMotion(reduced: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: reduced,
      media: query,
    })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('prefersReducedMotion', () => {
  it('returns false when matchMedia is unavailable (SSR/test env)', () => {
    vi.stubGlobal('matchMedia', undefined);
    expect(prefersReducedMotion()).toBe(false);
  });

  it('reflects the media query result', () => {
    stubReducedMotion(true);
    expect(prefersReducedMotion()).toBe(true);
    stubReducedMotion(false);
    expect(prefersReducedMotion()).toBe(false);
  });
});

describe('staggerDelay', () => {
  it('returns 0 for the first item', () => {
    expect(staggerDelay(0)).toBe(0);
  });

  it('scales linearly with index', () => {
    expect(staggerDelay(2)).toBe(120);
    expect(staggerDelay(3, { step: 30 })).toBe(90);
  });

  it('clamps to the max ceiling so long lists never stall', () => {
    expect(staggerDelay(100)).toBe(360);
    expect(staggerDelay(100, { step: 8, max: 340 })).toBe(340);
  });

  it('handles degenerate input', () => {
    expect(staggerDelay(-1)).toBe(0);
    expect(staggerDelay(2, { step: 0 })).toBe(0);
  });
});

describe('staggerStyle', () => {
  it('emits an animation-delay fragment', () => {
    expect(staggerStyle(2)).toBe('animation-delay: 120ms;');
    expect(staggerStyle(0, { step: 25 })).toBe('animation-delay: 0ms;');
  });
});

describe('transitions', () => {
  it('enter produces an opacity + rise transform', () => {
    const cfg = enter(node, { y: 8, duration: 300 });
    expect(cfg.duration).toBe(300);
    expect(cfg.css?.(0, 1)).toContain('opacity: 0');
    expect(cfg.css?.(0, 1)).toContain('translateY(8px)');
    expect(cfg.css?.(1, 0)).toContain('opacity: 1');
    expect(cfg.css?.(1, 0)).toContain('translateY(0px)');
  });

  it('enter scales when asked (dialog/cell pops)', () => {
    const cfg = enter(node, { scale: 0.95, duration: 200 });
    expect(cfg.css?.(0, 1)).toContain('scale(0.95)');
    expect(cfg.css?.(1, 0)).toContain('scale(1)');
  });

  it('presets share the same vocabulary', () => {
    expect(rise(node).css?.(0, 1)).toContain('translateY(8px)');
    expect(popIn(node).css?.(0, 1)).toContain('scale(0.5)');
    expect(dialogIn(node).css?.(0, 1)).toContain('scale(0.95)');
    expect(drawerIn(node).css?.(0, 1)).toContain('translateX(100%)');
    expect(growX(node).css?.(0, 1)).toContain('scaleX(0)');
    expect(growX(node).css?.(1, 0)).toContain('scaleX(1)');
    const b = backdropIn(node, { duration: 100 });
    expect(b.duration).toBe(100);
  });

  it('collapses to duration 0 under prefers-reduced-motion', () => {
    stubReducedMotion(true);
    for (const cfg of [
      enter(node, { y: 8 }),
      rise(node),
      popIn(node),
      dialogIn(node),
      drawerIn(node),
      growX(node),
      backdropIn(node),
    ]) {
      expect(cfg.duration).toBe(0);
    }
  });

  it('collapses when duration <= 0', () => {
    expect(enter(node, { duration: 0 }).duration).toBe(0);
  });
});

describe('tweenNumber', () => {
  it('jumps straight to the target under reduced motion', () => {
    stubReducedMotion(true);
    const onUpdate = vi.fn();
    const cancel = tweenNumber(0, 42, { onUpdate });
    expect(onUpdate).toHaveBeenCalledWith(42);
    expect(() => cancel()).not.toThrow();
  });

  it('jumps straight to the target when from === to or duration <= 0', () => {
    const a = vi.fn();
    tweenNumber(7, 7, { onUpdate: a });
    expect(a).toHaveBeenCalledWith(7);

    const b = vi.fn();
    tweenNumber(0, 9, { duration: 0, onUpdate: b });
    expect(b).toHaveBeenCalledWith(9);
  });

  it('eases between values via rAF and is cancellable', () => {
    const cbs: Array<(now: number) => void> = [];
    vi.stubGlobal('requestAnimationFrame', (cb: (now: number) => void) => {
      cbs.push(cb);
      return cbs.length;
    });
    const cancelMock = vi.fn();
    vi.stubGlobal('cancelAnimationFrame', cancelMock);

    const onUpdate = vi.fn();
    const cancel = tweenNumber(0, 100, {
      duration: MOTION_DURATION.enter,
      onUpdate,
    });
    expect(cbs.length).toBe(1);

    // Half-way tick — eased value between 0 and 100.
    cbs[0](performance.now() + MOTION_DURATION.enter / 2);
    const mid = onUpdate.mock.calls[0][0];
    expect(mid).toBeGreaterThan(0);
    expect(mid).toBeLessThan(100);

    // Final tick lands exactly on the target and stops scheduling.
    cbs[cbs.length - 1](performance.now() + MOTION_DURATION.enter + 10);
    expect(onUpdate).toHaveBeenLastCalledWith(100);

    cancel();
    expect(cancelMock).toHaveBeenCalled();
  });
});
