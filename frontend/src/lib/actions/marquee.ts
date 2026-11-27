/**
 * marquee — Svelte action that turns a `.pln-mq` container into an infinite
 * horizontal auto-scroll when its text overflows. Expects this structure:
 *
 *   <span class="pln-mq" use:marquee>
 *     <span class="pln-mq-track">
 *       <span class="pln-mq-text">title</span>
 *       <span class="pln-mq-text pln-mq-dup" aria-hidden="true">title</span>
 *     </span>
 *   </span>
 *
 * The animation only activates when the first copy is wider than the
 * container (`marquee-on` class). Each loop dwells with the title start in
 * view for `--mq-dwell` (default 1s) before scrolling resumes; the scroll
 * segment keeps a constant speed regardless of title length.
 *
 * The dwell is driven with the Web Animations API: keyframe offsets are
 * computed per cycle so the pause stays a fixed absolute time while the
 * scroll segment scales with the text width. The shared `pln-marquee` CSS
 * animation remains underneath as a no-WAAPI fallback (scroll without
 * dwell) — WAAPI output wins in the composite order, and the
 * `prefers-reduced-motion` media query still neutralises it.
 */

const SPEED_PX_PER_S = 32;
const MIN_SCROLL_S = 2;
const DEFAULT_DWELL_S = 1;

export interface MarqueeTiming {
  /** Full cycle length in milliseconds (dwell + scroll segment). */
  durationMs: number;
  /** Keyframe offset (0–1) where the hold ends and scrolling begins. */
  dwellFraction: number;
  /** Scroll segment length in seconds — also the CSS fallback duration. */
  scrollSeconds: number;
}

/**
 * Pure timing math for one marquee cycle: the scroll segment covers
 * `copyWidthPx` at a constant SPEED_PX_PER_S (clamped to a minimum), and a
 * fixed `dwellSeconds` hold is added on top. `dwellFraction` feeds the
 * WAAPI keyframe offsets so the pause is an absolute time, not a percentage
 * of the scroll.
 */
export function computeMarqueeTiming(
  copyWidthPx: number,
  dwellSeconds: number
): MarqueeTiming {
  const scrollSeconds = Math.max(copyWidthPx / SPEED_PX_PER_S, MIN_SCROLL_S);
  const dwell = Math.max(dwellSeconds, 0);
  const totalSeconds = scrollSeconds + dwell;
  return {
    durationMs: totalSeconds * 1000,
    dwellFraction: totalSeconds > 0 ? dwell / totalSeconds : 0,
    scrollSeconds,
  };
}

/**
 * Cycle keyframes: hold the title start in view for the dwell fraction,
 * then scroll one copy width (-50% of the track) at constant speed. The
 * loop wraps from -50% back to 0 seamlessly because the track's second copy
 * is identical and its leading padding is the loop gap.
 */
export function buildMarqueeKeyframes(
  timing: MarqueeTiming
): { transform: string; offset: number }[] {
  return [
    { transform: 'translateX(0)', offset: 0 },
    { transform: 'translateX(0)', offset: timing.dwellFraction },
    { transform: 'translateX(-50%)', offset: 1 },
  ];
}

/**
 * Parse the `--mq-dwell` CSS time value (`1s`, `250ms`, or a unitless number
 * of seconds). Falls back to DEFAULT_DWELL_S on missing/invalid input.
 */
export function parseDwellSeconds(raw: string | null | undefined): number {
  const match = raw?.trim().match(/^([0-9]*\.?[0-9]+)\s*(ms|s)?$/i);
  if (!match) return DEFAULT_DWELL_S;
  const value = Number.parseFloat(match[1]);
  if (!Number.isFinite(value) || value < 0) return DEFAULT_DWELL_S;
  return match[2]?.toLowerCase() === 'ms' ? value / 1000 : value;
}

export function marquee(node: HTMLElement) {
  let animation: Animation | null = null;
  let appliedKey = '';

  // jsdom and very old engines lack matchMedia — treat as "no preference".
  const motionQuery =
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-reduced-motion: reduce)')
      : null;

  function stop() {
    animation?.cancel();
    animation = null;
    appliedKey = '';
  }

  function check() {
    const track = node.querySelector<HTMLElement>('.pln-mq-track');
    const first = node.querySelector<HTMLElement>('.pln-mq-text');
    if (!track || !first) return;
    // Copy width includes the trailing padding that creates the loop gap.
    const copyWidth = first.offsetWidth;
    const overflows = copyWidth > node.clientWidth + 2;
    node.classList.toggle('marquee-on', overflows);
    if (!overflows) {
      track.style.animationDuration = '';
      stop();
      return;
    }

    const dwellSeconds = parseDwellSeconds(
      getComputedStyle(node).getPropertyValue('--mq-dwell')
    );
    const timing = computeMarqueeTiming(copyWidth, dwellSeconds);
    // CSS fallback duration covers only the scroll segment (no dwell).
    track.style.animationDuration = `${timing.scrollSeconds}s`;

    // Reduced motion: leave the CSS media query's static state in place.
    if (motionQuery?.matches || typeof track.animate !== 'function') {
      stop();
      return;
    }

    // Restart only when the timing actually changed — mutation/resize
    // callbacks fire often and must not reset the scroll position.
    const key = `${timing.durationMs}:${timing.dwellFraction}`;
    if (animation && key === appliedKey) return;
    stop();
    animation = track.animate(buildMarqueeKeyframes(timing), {
      duration: timing.durationMs,
      iterations: Infinity,
      easing: 'linear',
    });
    appliedKey = key;
  }

  // Children may render in the same tick — measure after the microtask flush.
  queueMicrotask(check);
  let ro: ResizeObserver | null = null;
  if (typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(check);
    ro.observe(node);
  }
  const mo = new MutationObserver(check);
  mo.observe(node, { childList: true, subtree: true, characterData: true });
  // React to live `prefers-reduced-motion` toggles.
  motionQuery?.addEventListener('change', check);

  return {
    destroy() {
      ro?.disconnect();
      mo.disconnect();
      motionQuery?.removeEventListener('change', check);
      stop();
    },
  };
}
