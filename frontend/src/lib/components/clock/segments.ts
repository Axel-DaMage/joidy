import type { ClockParts } from '$lib/utils/clock';

/** Parts needed to lay out a readout's digit groups. */
export type SegmentParts = Pick<ClockParts, 'hours' | 'minutes' | 'seconds' | 'h'>;

/**
 * Segment layout for a clock/timer readout (#1093).
 *
 * Readouts always reserve the full HH:MM:SS skeleton — three two-digit
 * groups separated by ':'. `ghostLead` counts the leading groups (plus
 * their separator) rendered as invisible in-flow placeholders: in timer
 * mode with `h === 0` the hours group ghosts, so MM:SS ↔ HH:MM:SS never
 * changes the node count, the box size or the position of the visible
 * digits (they stay right-aligned within the reserved skeleton).
 */
export interface ClockSegmentLayout {
  groups: [string, string, string];
  ghostLead: 0 | 1;
}

export function clockSegments(parts: SegmentParts, mode: 'clock' | 'timer'): ClockSegmentLayout {
  return {
    groups: [parts.hours, parts.minutes, parts.seconds],
    ghostLead: mode === 'timer' && parts.h <= 0 ? 1 : 0,
  };
}

/** Flat text for text-based styles: hidden leading part + always-visible body. */
export function segmentText(layout: ClockSegmentLayout): { ghost: string; body: string } {
  const [h, m, s] = layout.groups;
  return layout.ghostLead
    ? { ghost: `${h}:`, body: `${m}:${s}` }
    : { ghost: '', body: `${h}:${m}:${s}` };
}
