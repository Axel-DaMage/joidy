import { describe, it, expect } from 'vitest';
import type { CalendarTask } from '$lib/api';
import { dueTaskReminders, fireTaskNotification, REMINDER_LATE_GRACE_MS } from './taskReminders';

function task(overrides: Partial<CalendarTask>): CalendarTask {
  return {
    id: 1,
    title: 'Task',
    date: null,
    start_time: null,
    end_time: null,
    priority: 'MEDIUM',
    done: false,
    done_at: null,
    goal_id: null,
    source: 'JOIDY',
    google_event_id: null,
    color: null,
    recurrence: 'NONE',
    reminder_minutes: null,
    created_at: '',
    updated_at: '',
    ...overrides,
  };
}

// Fixed "today" so day-key comparisons are deterministic.
const NOW = new Date(2099, 7, 20, 11, 45, 0); // 2099-08-20 11:45 local
const TODAY = '2099-08-20';

describe('dueTaskReminders', () => {
  it('returns a task inside its reminder window', () => {
    const t = task({ id: 1, date: TODAY, start_time: '12:00:00', reminder_minutes: 15 });
    // 12:00 - 15min = 11:45 → exactly due at NOW.
    expect(dueTaskReminders([t], NOW, new Set())).toEqual([t]);
  });

  it('skips tasks before their reminder window opens', () => {
    const t = task({ id: 1, date: TODAY, start_time: '12:01:00', reminder_minutes: 15 });
    expect(dueTaskReminders([t], NOW, new Set())).toEqual([]);
  });

  it('skips done, notified and unscheduled tasks', () => {
    const done = task({
      id: 2,
      date: TODAY,
      start_time: '12:00:00',
      reminder_minutes: 15,
      done: true,
    });
    const already = task({ id: 3, date: TODAY, start_time: '12:00:00', reminder_minutes: 15 });
    const floating = task({ id: 4, date: null, start_time: '12:00:00', reminder_minutes: 15 });
    expect(dueTaskReminders([done, already, floating], NOW, new Set([3]))).toEqual([]);
  });

  it('skips tasks without start_time or reminder', () => {
    const noTime = task({ id: 5, date: TODAY, reminder_minutes: 15 });
    const noReminder = task({ id: 6, date: TODAY, start_time: '12:00:00' });
    const otherDay = task({
      id: 7,
      date: '2099-08-21',
      start_time: '12:00:00',
      reminder_minutes: 15,
    });
    expect(dueTaskReminders([noTime, noReminder, otherDay], NOW, new Set())).toEqual([]);
  });

  it('stops firing long after the start time (late grace)', () => {
    const t = task({ id: 8, date: TODAY, start_time: '09:00:00', reminder_minutes: 15 });
    const within = new Date(2099, 7, 20, 9, 30, 0);
    expect(dueTaskReminders([t], within, new Set())).toEqual([t]);
    // Hours past start → stale, not "due".
    const stale = new Date(within.getTime() + REMINDER_LATE_GRACE_MS + 1);
    expect(dueTaskReminders([t], stale, new Set())).toEqual([]);
  });
});

describe('fireTaskNotification', () => {
  it('returns false when the Notification API is unavailable', () => {
    // Node/vitest has no window.Notification.
    expect(fireTaskNotification('Title', 'Body')).toBe(false);
  });
});
