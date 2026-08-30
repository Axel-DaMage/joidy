/**
 * Shared goal color presets used across goals/+page.svelte and goals/[id]/+page.svelte.
 * Extracted to eliminate duplication and hardcoded hex values in routes (#256).
 */
export interface GoalColorPreset {
  name: string;
  hex: string;
}

export const GOAL_COLOR_PRESETS: GoalColorPreset[] = [
  { name: 'Rojo',      hex: '#ef4444' },
  { name: 'Coral',     hex: '#f97316' },
  { name: 'Ámbar',     hex: '#f59e0b' },
  { name: 'Lima',      hex: '#84cc16' },
  { name: 'Esmeralda', hex: '#10b981' },
  { name: 'Cian',      hex: '#06b6d4' },
  { name: 'Azul',      hex: '#3b82f6' },
  { name: 'Violeta',   hex: '#8b5cf6' },
  { name: 'Rosa',      hex: '#ec4899' },
  { name: 'Slate',     hex: '#64748b' },
];

export const GOALS_SPECIFIC_COLOR_PRESETS = GOAL_COLOR_PRESETS.slice(0, 8);

export const DEFAULT_GOAL_COLOR = '#c8a96e';

/** Temporality color mapping — used by goal cards and editors. */
export const TEMPORALITY_COLORS: Record<string, string> = {
  'DAILY':   '#c8a96e',
  'WEEKLY':  '#22d3d3',
  'MONTHLY': '#a78bfa',
  'ANNUAL':  '#f59e0b',
};
