import type { ClockParts } from '$lib/utils/clock';

/**
 * Common contract implemented by every clock-style component (#707).
 *
 * - `mode='clock'` renders wall time (HH:MM:SS); `mode='timer'` renders a
 *   countdown readout.
 * - `progress` is the remaining fraction (0..1), only meaningful in timer mode.
 * - `size` is a hint; text-based styles scale off the host `font-size` (em),
 *   dial-based styles map it to a pixel footprint.
 */
export interface ClockStyleProps extends ClockParts {
  mode: 'clock' | 'timer';
  progress?: number;
  size?: 'sm' | 'md' | 'lg';
}
