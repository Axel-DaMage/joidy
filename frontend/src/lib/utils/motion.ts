// Shared motion language (#1657), extracted from the analytics module
// (`lib/components/analytics/` — ChartCard entrances, heatmap cell pop-in,
// bar grows, skeleton shimmer, CountUp).
//
// Two layers:
//   - CSS utilities in `app.css` (section "Motion system"): `.m-rise`,
//     `.m-pop`, `.m-fade`, `.m-grow-x`, `.m-lift`, `.m-skeleton`, driven by
//     the `--m-i` custom property for per-item stagger.
//   - The Svelte transitions and JS helpers below for imperative motion:
//     page transitions, overlays, toasts, list entrances, count-ups.
//
// `prefers-reduced-motion` is honored twice: the global `@media` block in
// `app.css` collapses every CSS animation/transition to ~0ms, and every
// helper below returns duration 0 / jumps to the final state when
// `prefersReducedMotion()` is true.

import { cubicOut } from 'svelte/easing';
import { fade } from 'svelte/transition';
import type { TransitionConfig } from 'svelte/transition';

/**
 * Canonical easing — the same curve as `--ease-out` in `app.css` and the
 * `cubic-bezier(0.2, 0.7, 0.2, 1)` used across the analytics components.
 * (`svelte/easing` has no cubic-bezier primitive; `cubicOut` is the closest
 * stock curve and is visually indistinguishable at these durations.)
 */
export const MOTION_EASE = 'cubic-bezier(0.2, 0.7, 0.2, 1)';

/**
 * Duration scale in ms. `fast`/`normal`/`slow` mirror the
 * `--t-fast`/`--t-normal`/`--t-slow` tokens in `app.css` for
 * micro-interactions; `enter`/`grow`/`fade` are the longer beats the
 * analytics components already established for entrances (0.45s rise),
 * bar growth (0.7s) and overlays (150ms).
 */
export const MOTION_DURATION = {
  fast: 50,
  normal: 80,
  slow: 120,
  enter: 450,
  grow: 700,
  fade: 150,
} as const;

/** Current reduced-motion preference. False during SSR / test envs. */
export function prefersReducedMotion(): boolean {
  return (
    typeof matchMedia === 'function' &&
    matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

export interface StaggerOptions {
  /** Delay between consecutive items (ms). Analytics uses 60ms for cards
   *  and ~8ms for dense grids like the consistency heatmap. */
  step?: number;
  /** Hard ceiling so long lists never stall the entrance (ms). */
  max?: number;
}

/**
 * Millisecond delay for a staggered entrance — `index * step` clamped to
 * `max`. Pass it to a transition (`in:rise={{ delay }}`) or to
 * `staggerStyle()` for CSS `m-*` classes.
 */
export function staggerDelay(
  index: number,
  { step = 60, max = 360 }: StaggerOptions = {},
): number {
  if (index <= 0 || step <= 0) return 0;
  return Math.min(index * step, max);
}

/** Inline-style fragment applying a staggered `animation-delay` for `m-*` classes. */
export function staggerStyle(index: number, opts: StaggerOptions = {}): string {
  return `animation-delay: ${staggerDelay(index, opts)}ms;`;
}

export interface EnterParams {
  delay?: number;
  /** ms — default `MOTION_DURATION.enter` (450ms, the analytics beat). */
  duration?: number;
  /** px the element rises from (analytics entrances use 4–8px). */
  y?: number;
  /** px the element slides from on the x axis (negative = from the left). */
  x?: number;
  /** Initial scale (1 = none; 0.95 = dialog pop; 0.5 = heatmap cell). */
  scale?: number;
  /** transform-origin for the scale part. */
  origin?: string;
}

/**
 * Core entrance transition: fade + optional rise/slide/zoom in a single
 * cubic-out beat. One primitive covering card entrances, page transitions,
 * dialogs, toasts and pop-ins. Collapses to duration 0 under
 * `prefers-reduced-motion`.
 */
export function enter(_node: Element, params: EnterParams = {}): TransitionConfig {
  const {
    delay = 0,
    duration = MOTION_DURATION.enter,
    y = 0,
    x = 0,
    scale = 1,
    origin = 'center',
  } = params;
  if (prefersReducedMotion() || duration <= 0) return { duration: 0 };
  return {
    delay,
    duration,
    easing: cubicOut,
    css: (t) => {
      const parts: string[] = [];
      if (y) parts.push(`translateY(${(1 - t) * y}px)`);
      if (x) parts.push(`translateX(${(1 - t) * x}px)`);
      if (scale !== 1) parts.push(`scale(${scale + (1 - scale) * t})`);
      const transform = parts.length ? parts.join(' ') : 'none';
      return `opacity: ${t}; transform: ${transform}; transform-origin: ${origin};`;
    },
  };
}

/** Card/row/page entrance — the `ac-in`/`ad-fade` fade + 8px rise beat. */
export function rise(
  node: Element,
  params: Omit<EnterParams, 'x' | 'scale'> = {},
): TransitionConfig {
  return enter(node, { y: 8, ...params });
}

/** Cell/chip pop-in — the heatmap `hm-pop` scale(0.5)→1 beat. */
export function popIn(
  node: Element,
  params: Omit<EnterParams, 'x' | 'y'> = {},
): TransitionConfig {
  return enter(node, { scale: 0.5, ...params });
}

/** Dialog entrance — `svelte/transition` scale({ start: 0.95 }) equivalent. */
export function dialogIn(
  node: Element,
  params: Omit<EnterParams, 'x' | 'y'> = {},
): TransitionConfig {
  return enter(node, { scale: 0.95, duration: 200, ...params });
}

/**
 * Drawer entrance — slides in from the edge (default: 100% from the right,
 * the SettingsPanel beat). Pass `x: -100` for a left drawer.
 */
export function drawerIn(
  _node: Element,
  params: { delay?: number; duration?: number; x?: number } = {},
): TransitionConfig {
  const { delay = 0, duration = 180, x = 100 } = params;
  if (prefersReducedMotion() || duration <= 0) return { duration: 0 };
  return {
    delay,
    duration,
    easing: cubicOut,
    css: (t) => `opacity: ${t}; transform: translateX(${(1 - t) * x}%);`,
  };
}

/** Bar/sparkline grow — `scaleX(0)→1`, GPU-only (the `*-grow` keyframes). */
export function growX(
  _node: Element,
  params: { delay?: number; duration?: number } = {},
): TransitionConfig {
  const { delay = 0, duration = MOTION_DURATION.grow } = params;
  if (prefersReducedMotion() || duration <= 0) return { duration: 0 };
  return {
    delay,
    duration,
    easing: cubicOut,
    css: (t) => `transform: scaleX(${t}); transform-origin: left center;`,
  };
}

/** Overlay scrim — plain fade, the modal/palette backdrop beat. */
export function backdropIn(
  node: Element,
  params: { delay?: number; duration?: number } = {},
): TransitionConfig {
  const { delay = 0, duration = MOTION_DURATION.fade } = params;
  if (prefersReducedMotion() || duration <= 0) return { duration: 0 };
  return fade(node, { delay, duration, easing: cubicOut });
}

export interface TweenNumberOptions {
  /** ms — default `MOTION_DURATION.grow` (700ms, the CountUp beat). */
  duration?: number;
  easing?: (t: number) => number;
  onUpdate: (value: number) => void;
}

/**
 * rAF count-up — eases a number from `from` to `to`. Returns a cancel
 * function. Under `prefers-reduced-motion`, `duration <= 0` or
 * `from === to` it jumps straight to `to` and the cancel is a no-op.
 * This is the imperative twin of `lib/components/CountUp.svelte`.
 */
export function tweenNumber(
  from: number,
  to: number,
  { duration = MOTION_DURATION.grow, easing = cubicOut, onUpdate }: TweenNumberOptions,
): () => void {
  if (
    prefersReducedMotion() ||
    duration <= 0 ||
    from === to ||
    typeof requestAnimationFrame !== 'function'
  ) {
    onUpdate(to);
    return () => {};
  }
  const start = performance.now();
  let raf = requestAnimationFrame(function tick(now) {
    const p = Math.min(1, (now - start) / duration);
    onUpdate(from + (to - from) * easing(p));
    if (p < 1) raf = requestAnimationFrame(tick);
  });
  return () => cancelAnimationFrame(raf);
}
