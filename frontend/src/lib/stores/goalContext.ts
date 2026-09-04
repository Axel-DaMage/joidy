import { getContext, setContext } from 'svelte';
import type { Goal, Note, Tag } from '$lib/api';

/**
 * Shared context for goal-related components, eliminating prop drilling
 * through GoalList → GoalCard (#351). The parent page sets this once and
 * GoalCard reads whatever it needs via getContext.
 */
export interface GoalContextValue {
  tags: Tag[];
  notes: Note[];
  getGoalColor: (goal: Goal) => string;
  TEMPORALITY_LABELS: Record<string, string>;
  STATE_LABELS: Record<string, string>;
  formatFailConfig: (config: string) => string;
  onTogglePin: (id: number) => void;
  onClick: (goal: Goal) => void;
  onComplete?: (id: number) => void;
  onFail?: (id: number) => void;
  onDelete?: (id: number) => void;
  onArchive?: (id: number) => void;
}

const KEY = Symbol('goal-context');

export function setGoalContext(ctx: GoalContextValue): void {
  setContext(KEY, ctx);
}

export function getGoalContext(): GoalContextValue | undefined {
  return getContext<GoalContextValue>(KEY);
}
