import type { ClockParts } from '$lib/utils/clock';

/**
 * Common contract implemented by every clock-style component (#707).
 *
 * - `mode='clock'` renders wall time (HH:MM:SS); `mode='timer'` renders a
 *   countdown readout.
 * - `progress` is the remaining fraction (0..1), only meaningful in timer mode.
 * - `size` is a hint; text-based styles scale off the host `font-size` (em),
 *   dial-based styles map it to a pixel footprint.
 *
 * ── Common box metric (#1093) ────────────────────────────────────────────
 * Every style renders inside the fixed `.clock-frame` wrapper of
 * ClockDisplay.svelte, so toggling styles or timer shapes never resizes or
 * shifts the surface (widget `.timer` at 32px, focus mode at 48px share the
 * same proportions because every dimension below is em/ch-relative):
 *
 * 1. Typography — the frame sets `font-family: var(--font-mono, monospace)`
 *    and `font-variant-numeric: tabular-nums`; styles inherit both.
 *    Per-style font-weight is allowed: monospace keeps digit advances equal.
 * 2. Skeleton — readouts always render the HH:MM:SS shape (3 two-digit
 *    groups + separators, see ./segments.ts). In timer mode with `h === 0`
 *    the hours group ghosts in-flow (`visibility: hidden`), reserving its
 *    space so MM:SS ↔ HH:MM:SS never moves the visible digits. Exception:
 *    the circular dial centers its own readout inside its fixed ring.
 * 3. Frame — fixed `min-height: 1.5em` and reserved
 *    `min-width: calc(8ch + 2em)`, content centered; the `size` hint only
 *    scales the frame font-size (0.85em / 1em / 1.15em off the host).
 * 4. Cells — boxed styles share radius `0.14em`–`0.2em` and slim padding
 *    (~0.12em vertical); decorations must stay within the frame (≤ 1.5em
 *    tall, ≤ 8ch + 2em wide).
 * 5. Async — while a lazy style chunk loads, a same-size skeleton occupies
 *    the frame, so the fallback never flashes at a different size.
 */
export interface ClockStyleProps extends ClockParts {
  mode: 'clock' | 'timer';
  progress?: number;
  size?: 'sm' | 'md' | 'lg';
}
