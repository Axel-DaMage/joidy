/**
 * Shared goal color presets used across goals/+page.svelte and goals/[id]/+page.svelte.
 * Extracted to eliminate duplication and hardcoded hex values in routes (#256).
 */
export interface GoalColorPreset {
  name: string;
  hex: string;
}

export const GOAL_COLOR_PRESETS: GoalColorPreset[] = [
  { name: 'Gold',      hex: '#c8a96e' },
  { name: 'Esmeralda', hex: '#10b981' },
  { name: 'Cyan',      hex: '#06b6d4' },
  { name: 'Azul',      hex: '#3b82f6' },
  { name: 'Violeta',   hex: '#8b5cf6' },
  { name: 'Rosa',      hex: '#ec4899' },
  { name: 'Ámbar',     hex: '#f59e0b' },
  { name: 'Coral',     hex: '#ef4444' },
  { name: 'Lima',      hex: '#84cc16' },
  { name: 'Slate',     hex: '#64748b' },
  { name: 'Teal',      hex: '#14b8a6' },
  { name: 'Blanco',    hex: '#e2e8f0' },
];

export const DEFAULT_GOAL_COLOR = '#c8a96e';

/** Temporality color mapping — used by goal cards and editors. */
export const TEMPORALITY_COLORS: Record<string, string> = {
  'DAILY':   '#c8a96e',
  'WEEKLY':  '#22d3d3',
  'MONTHLY': '#a78bfa',
  'ANNUAL':  '#f59e0b',
};
