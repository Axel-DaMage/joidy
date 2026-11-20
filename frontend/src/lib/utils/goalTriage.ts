import type { Goal, GoalContext } from '$lib/api';

/**
 * Inbox triage helpers (#1200).
 *
 * Inbox goals (state='INBOX') are low-friction captures waiting to be
 * classified. Triage picks an energy context and a coarse priority level
 * which maps onto the fine-grained `priority` numeric field (#1097,
 * higher wins, 0-99) so triaged items land in sensible queue positions.
 */

export type InboxPriority = 'P0' | 'P1' | 'P2';

/** Coarse triage levels → numeric `priority` (higher = more urgent). */
export const INBOX_PRIORITY_VALUES: Record<InboxPriority, number> = {
  P0: 90,
  P1: 50,
  P2: 10,
};

export const GOAL_CONTEXTS: GoalContext[] = ['ANY', 'MORNING', 'NIGHT'];
export const INBOX_PRIORITIES: InboxPriority[] = ['P0', 'P1', 'P2'];

export function inboxGoals(goals: Goal[]): Goal[] {
  return goals.filter((g) => g.state === 'INBOX');
}

export function inboxCount(goals: Goal[]): number {
  return inboxGoals(goals).length;
}

/**
 * Suggested triage priority for an inbox goal: bucket its current numeric
 * priority into the nearest P-level so the UI reflects stored values.
 */
export function suggestedInboxPriority(priority: number | null | undefined): InboxPriority {
  const p = priority ?? 0;
  if (p >= 70) return 'P0';
  if (p >= 30) return 'P1';
  return 'P2';
}

/** Payload sent when moving an inbox goal into the active execution queue. */
export function triagePayload(context: GoalContext, priority: InboxPriority) {
  return {
    state: 'ACTIVE' as const,
    context,
    priority: INBOX_PRIORITY_VALUES[priority],
  };
}
