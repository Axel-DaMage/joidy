import { describe, it, expect } from 'vitest';
import {
  INBOX_PRIORITY_VALUES,
  inboxGoals,
  inboxCount,
  suggestedInboxPriority,
  triagePayload,
} from './goalTriage';
import type { Goal } from '$lib/api';

function makeGoal(overrides: Partial<Goal> = {}): Goal {
  return {
    id: 1,
    title: 'Goal',
    description: '',
    source_path: null,
    temporality: 'ONEOFF',
    context: 'ANY',
    measurement_type: 'COUNT',
    target_value: 1,
    current_value: 0,
    state: 'ACTIVE',
    fail_config: 'STATIC',
    fail_emoji: '🔴',
    color: '#c8a96e',
    theme: 'solid',
    note_id: null,
    tag_id: null,
    parent_id: null,
    max_assignment_days: null,
    priority: 0,
    progress_pct: 0,
    pending_removal: false,
    is_completed: false,
    completed_at: null,
    created_at: '2024-03-15T10:00:00',
    updated_at: '2024-03-15T10:00:00',
    ...overrides,
  };
}

describe('goalTriage — inboxGoals', () => {
  it('filters only INBOX goals', () => {
    const goals = [
      makeGoal({ id: 1, state: 'INBOX' }),
      makeGoal({ id: 2, state: 'ACTIVE' }),
      makeGoal({ id: 3, state: 'INBOX' }),
      makeGoal({ id: 4, state: 'COMPLETED' }),
    ];
    const inbox = inboxGoals(goals);
    expect(inbox.map((g) => g.id)).toEqual([1, 3]);
    expect(inboxCount(goals)).toBe(2);
  });

  it('returns empty array when no inbox goals', () => {
    expect(inboxGoals([makeGoal()])).toEqual([]);
  });
});

describe('goalTriage — INBOX_PRIORITY_VALUES', () => {
  it('orders P0 > P1 > P2 within the 0-99 backend range', () => {
    expect(INBOX_PRIORITY_VALUES.P0).toBe(90);
    expect(INBOX_PRIORITY_VALUES.P1).toBe(50);
    expect(INBOX_PRIORITY_VALUES.P2).toBe(10);
    expect(INBOX_PRIORITY_VALUES.P0).toBeGreaterThan(INBOX_PRIORITY_VALUES.P1);
    expect(INBOX_PRIORITY_VALUES.P1).toBeGreaterThan(INBOX_PRIORITY_VALUES.P2);
  });
});

describe('goalTriage — suggestedInboxPriority', () => {
  it('buckets numeric priority into P-levels', () => {
    expect(suggestedInboxPriority(95)).toBe('P0');
    expect(suggestedInboxPriority(70)).toBe('P0');
    expect(suggestedInboxPriority(50)).toBe('P1');
    expect(suggestedInboxPriority(30)).toBe('P1');
    expect(suggestedInboxPriority(10)).toBe('P2');
    expect(suggestedInboxPriority(0)).toBe('P2');
    expect(suggestedInboxPriority(undefined)).toBe('P2');
    expect(suggestedInboxPriority(null)).toBe('P2');
  });
});

describe('goalTriage — triagePayload', () => {
  it('builds the activation payload with mapped priority', () => {
    expect(triagePayload('MORNING', 'P0')).toEqual({
      state: 'ACTIVE',
      context: 'MORNING',
      priority: 90,
    });
    expect(triagePayload('NIGHT', 'P2')).toEqual({
      state: 'ACTIVE',
      context: 'NIGHT',
      priority: 10,
    });
  });
});
