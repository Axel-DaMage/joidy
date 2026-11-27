import { describe, it, expect } from 'vitest';
import {
  buildHistoryEvents,
  computeHistoryStats,
  daysBeforeKey,
  groupHistoryEvents,
  nextDayKey,
  type HistoryEvent,
} from './goalsHistory';
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

function makeEvent(date: string, kind: HistoryEvent['kind'] = 'COMPLETED', id = 1): HistoryEvent {
  return { goal: makeGoal({ id }), kind, date, time: null };
}

describe('buildHistoryEvents', () => {
  it('maps terminal states to feed entries with day keys', () => {
    const events = buildHistoryEvents([
      makeGoal({ id: 1, state: 'COMPLETED', completed_at: '2024-03-10T09:30:00' }),
      makeGoal({ id: 2, state: 'FAILED', updated_at: '2024-03-11T18:00:00' }),
      makeGoal({ id: 3, state: 'CANCELLED', updated_at: '2024-03-12T08:00:00' }),
    ]);
    expect(events.map((e) => e.kind)).toEqual(['CANCELLED', 'FAILED', 'COMPLETED']);
    expect(events.map((e) => e.date)).toEqual(['2024-03-12', '2024-03-11', '2024-03-10']);
  });

  it('treats is_completed as completed even without COMPLETED state', () => {
    const events = buildHistoryEvents([
      makeGoal({ id: 1, state: 'ACTIVE', is_completed: true, completed_at: '2024-03-10T09:00:00' }),
    ]);
    expect(events).toHaveLength(1);
    expect(events[0].kind).toBe('COMPLETED');
  });

  it('skips active goals and terminal states without a timestamp', () => {
    const events = buildHistoryEvents([
      makeGoal({ id: 1, state: 'ACTIVE' }),
      makeGoal({ id: 2, state: 'COMPLETED', completed_at: null }),
      makeGoal({ id: 3, state: 'FAILED', updated_at: '' }),
    ]);
    expect(events).toHaveLength(0);
  });

  it('sorts newest-first, then by time, then by goal id', () => {
    const events = buildHistoryEvents([
      makeGoal({ id: 5, state: 'COMPLETED', completed_at: '2024-03-10T08:00:00' }),
      makeGoal({ id: 3, state: 'COMPLETED', completed_at: '2024-03-10T09:00:00' }),
      makeGoal({ id: 9, state: 'COMPLETED', completed_at: '2024-03-10T09:00:00' }),
    ]);
    expect(events.map((e) => e.goal.id)).toEqual([9, 3, 5]);
  });
});

describe('groupHistoryEvents', () => {
  it('groups adjacent same-day events preserving order', () => {
    const groups = groupHistoryEvents([
      makeEvent('2024-03-12', 'COMPLETED', 1),
      makeEvent('2024-03-12', 'FAILED', 2),
      makeEvent('2024-03-10', 'COMPLETED', 3),
    ]);
    expect(groups.map((g) => g.date)).toEqual(['2024-03-12', '2024-03-10']);
    expect(groups[0].items.map((e) => e.goal.id)).toEqual([1, 2]);
  });

  it('returns an empty array for an empty feed', () => {
    expect(groupHistoryEvents([])).toEqual([]);
  });
});

describe('computeHistoryStats', () => {
  it('counts states and computes effectiveness over decided events', () => {
    const stats = computeHistoryStats([
      makeEvent('2024-03-12', 'COMPLETED'),
      makeEvent('2024-03-12', 'COMPLETED', 2),
      makeEvent('2024-03-11', 'FAILED', 3),
      makeEvent('2024-03-10', 'CANCELLED', 4),
    ]);
    expect(stats.completed).toBe(2);
    expect(stats.failed).toBe(1);
    expect(stats.cancelled).toBe(1);
    // 2 / (2 + 1) — cancelled does not count as a decision.
    expect(stats.effectiveness).toBe(67);
  });

  it('returns null effectiveness when nothing was decided', () => {
    expect(computeHistoryStats([makeEvent('2024-03-10', 'CANCELLED')]).effectiveness).toBeNull();
    expect(computeHistoryStats([]).effectiveness).toBeNull();
  });

  it('computes the best streak of consecutive completion days', () => {
    const stats = computeHistoryStats([
      makeEvent('2024-03-12', 'COMPLETED'),
      makeEvent('2024-03-11', 'COMPLETED', 2),
      makeEvent('2024-03-11', 'COMPLETED', 3), // same day — counts once
      makeEvent('2024-03-09', 'COMPLETED', 4), // gap at 03-10
      makeEvent('2024-03-08', 'COMPLETED', 5),
    ]);
    expect(stats.bestStreak).toBe(2);
  });

  it('handles streaks across month boundaries', () => {
    const stats = computeHistoryStats([
      makeEvent('2024-04-01', 'COMPLETED'),
      makeEvent('2024-03-31', 'COMPLETED', 2),
      makeEvent('2024-03-30', 'COMPLETED', 3),
    ]);
    expect(stats.bestStreak).toBe(3);
  });
});

describe('day-key helpers', () => {
  it('nextDayKey rolls over month and year ends', () => {
    expect(nextDayKey('2024-03-31')).toBe('2024-04-01');
    expect(nextDayKey('2024-12-31')).toBe('2025-01-01');
  });

  it('daysBeforeKey walks back across boundaries', () => {
    expect(daysBeforeKey('2024-03-01', 7)).toBe('2024-02-24'); // 2024 is a leap year
    expect(daysBeforeKey('2024-03-10', 1)).toBe('2024-03-10');
  });
});
