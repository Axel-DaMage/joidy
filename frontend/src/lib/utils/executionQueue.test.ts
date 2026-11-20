import { describe, it, expect } from 'vitest';
import {
  EXECUTION_QUEUE_MORNING_CUTOFF_HOUR,
  buildExecutionQueue,
  resolveExecutionContext,
} from './executionQueue';
import type { CalendarTask, Goal } from '$lib/api';

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

function makeTask(overrides: Partial<CalendarTask> = {}): CalendarTask {
  return {
    id: 1,
    title: 'Task',
    date: '2024-03-15',
    start_time: null,
    end_time: null,
    priority: 'MEDIUM',
    done: false,
    done_at: null,
    goal_id: null,
    source: 'JOIDY',
    google_event_id: null,
    color: null,
    created_at: '2024-03-15T08:00:00',
    updated_at: '2024-03-15T08:00:00',
    ...overrides,
  };
}

describe('executionQueue — resolveExecutionContext', () => {
  it('resolves MORNING before the cutoff hour and NIGHT at/after it', () => {
    expect(EXECUTION_QUEUE_MORNING_CUTOFF_HOUR).toBe(15);
    expect(resolveExecutionContext(0)).toBe('MORNING');
    expect(resolveExecutionContext(8)).toBe('MORNING');
    expect(resolveExecutionContext(14)).toBe('MORNING');
    expect(resolveExecutionContext(15)).toBe('NIGHT');
    expect(resolveExecutionContext(21)).toBe('NIGHT');
    expect(resolveExecutionContext(23)).toBe('NIGHT');
  });
});

describe('executionQueue — buildExecutionQueue', () => {
  it('returns an empty list for two empty queues', () => {
    expect(buildExecutionQueue([], [])).toEqual([]);
  });

  it('orders goals by numeric priority descending', () => {
    const queue = buildExecutionQueue(
      [
        makeGoal({ id: 1, title: 'Low', priority: 10 }),
        makeGoal({ id: 2, title: 'High', priority: 90 }),
        makeGoal({ id: 3, title: 'Mid', priority: 50 }),
      ],
      []
    );
    expect(queue.map((i) => i.key)).toEqual(['goal-2', 'goal-3', 'goal-1']);
  });

  it('interleaves goals and tasks by mapped priority score', () => {
    const queue = buildExecutionQueue(
      [
        makeGoal({ id: 1, title: 'P1 goal', priority: 50 }),
        makeGoal({ id: 2, title: 'P0 goal', priority: 90 }),
      ],
      [
        makeTask({ id: 10, title: 'Urgent task', priority: 'URGENT' }), // score 95
        makeTask({ id: 11, title: 'Low task', priority: 'LOW' }), // score 25
      ]
    );
    expect(queue.map((i) => i.key)).toEqual([
      'task-10', // 95
      'goal-2', // 90
      'goal-1', // 50
      'task-11', // 25
    ]);
  });

  it('breaks score ties by start_time, then title — timeless tasks last', () => {
    const queue = buildExecutionQueue(
      [],
      [
        makeTask({ id: 1, title: 'Timeless', priority: 'HIGH' }),
        makeTask({ id: 2, title: 'Timed late', priority: 'HIGH', start_time: '18:30:00' }),
        makeTask({ id: 3, title: 'Timed early', priority: 'HIGH', start_time: '09:15:00' }),
      ]
    );
    expect(queue.map((i) => i.key)).toEqual(['task-3', 'task-2', 'task-1']);
    expect(queue[0].startTime).toBe('09:15');
  });

  it('puts the true top item first across both queues', () => {
    // A high-priority goal beats every non-URGENT task; an URGENT task beats
    // every goal below score 95.
    const queue = buildExecutionQueue(
      [makeGoal({ id: 1, title: 'Top goal', priority: 99 })],
      [makeTask({ id: 2, title: 'Urgent task', priority: 'URGENT' })]
    );
    expect(queue[0].key).toBe('goal-1');
    expect(queue[1].key).toBe('task-2');
  });
});
