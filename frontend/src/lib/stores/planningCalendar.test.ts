import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

const { apiMock, patchUserSettingsMock } = vi.hoisted(() => ({
  apiMock: {
    planning: {
      getAssignments: vi.fn(),
      setAssignments: vi.fn(),
    },
  },
  patchUserSettingsMock: vi.fn(),
}));

vi.mock('$lib/api', () => ({ api: apiMock }));

vi.mock('$lib/utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), log: vi.fn(), debug: vi.fn() },
}));

vi.mock('$lib/utils/userSettings', () => ({
  loadUserSettings: vi.fn(() => ({})),
  patchUserSettings: patchUserSettingsMock,
}));

import {
  CALENDAR_LAYERS,
  CHIP_DENSITY_LIMITS,
  DEFAULT_CALENDAR_LAYERS,
  agendaDaysFor,
  assignGoal,
  assignedIdsForDate,
  calendarLayers,
  chipDensity,
  getNormalizedDate,
  loadAssignmentsForDate,
  monthCellsFor,
  normalizedKeysForDate,
  planningAssignments,
  planningCursor,
  planningSelectedDay,
  planningView,
  selectPlanningDay,
  setChipDensity,
  setPlanningView,
  shiftPlanningPeriod,
  toggleCalendarLayer,
  unassignGoal,
  weekDaysFor,
} from './planningCalendar';

beforeEach(() => {
  apiMock.planning.getAssignments.mockReset();
  apiMock.planning.setAssignments.mockReset().mockResolvedValue({ date: '', goal_ids: [] });
  patchUserSettingsMock.mockReset();
  planningAssignments.set({});
  planningCursor.set('2024-06-15');
  planningView.set('month');
  planningSelectedDay.set(null);
  calendarLayers.set({ ...DEFAULT_CALENDAR_LAYERS });
  chipDensity.set('comfortable');
});

describe('getNormalizedDate', () => {
  it('keeps DAILY/ONEOFF dates as day keys', () => {
    expect(getNormalizedDate('2024-06-12', 'DAILY')).toBe('2024-06-12');
    expect(getNormalizedDate('2024-06-12', 'ONEOFF')).toBe('2024-06-12');
  });

  it('normalizes WEEKLY to the Monday of the week', () => {
    // 2024-06-12 is a Wednesday → Monday is 2024-06-10.
    expect(getNormalizedDate('2024-06-12', 'WEEKLY')).toBe('2024-06-10');
    // A Sunday belongs to the week that started the previous Monday.
    expect(getNormalizedDate('2024-06-16', 'WEEKLY')).toBe('2024-06-10');
  });

  it('normalizes MONTHLY to the 1st and ANNUAL to Jan 1st', () => {
    expect(getNormalizedDate('2024-06-12', 'MONTHLY')).toBe('2024-06-01');
    expect(getNormalizedDate('2024-06-12', 'ANNUAL')).toBe('2024-01-01');
  });
});

describe('grid helpers', () => {
  it('monthCellsFor returns 42 Monday-first cells covering the month', () => {
    const cells = monthCellsFor('2024-06-15');
    expect(cells).toHaveLength(42);
    expect(cells[0].iso).toBe('2024-05-27'); // Monday before June 1st (Sat)
    expect(cells.filter((c) => c.inMonth)).toHaveLength(30);
    expect(cells.find((c) => c.iso === '2024-06-01')?.inMonth).toBe(true);
  });

  it('weekDaysFor returns the 7 days of the containing week', () => {
    const days = weekDaysFor('2024-06-12');
    expect(days).toHaveLength(7);
    expect(days[0]).toBe('2024-06-10');
    expect(days[6]).toBe('2024-06-16');
  });

  it('agendaDaysFor returns consecutive days from the cursor', () => {
    const days = agendaDaysFor('2024-06-12', 3);
    expect(days).toEqual(['2024-06-12', '2024-06-13', '2024-06-14']);
  });
});

describe('normalizedKeysForDate / assignedIdsForDate', () => {
  it('covers the day, week, month and year buckets of a date', () => {
    const keys = normalizedKeysForDate('2024-06-12');
    expect(keys).toEqual(
      expect.arrayContaining(['2024-06-12', '2024-06-10', '2024-06-01', '2024-01-01'])
    );
  });

  it('unions ids from every bucket the date belongs to, deduplicated', () => {
    const map = {
      '2024-06-12': [1, 2],
      '2024-06-10': [2, 3],
      '2024-06-01': [4],
      '2024-01-01': [5],
    };
    expect(assignedIdsForDate(map, '2024-06-12').sort()).toEqual([1, 2, 3, 4, 5]);
  });
});

describe('view + selection state', () => {
  it('setPlanningView persists the view under calendarUi', () => {
    setPlanningView('week');
    expect(get(planningView)).toBe('week');
    expect(patchUserSettingsMock).toHaveBeenCalledWith({ calendarUi: { view: 'week' } });
  });

  it('shiftPlanningPeriod moves by month in month view and by week otherwise', () => {
    planningView.set('month');
    shiftPlanningPeriod(1);
    expect(get(planningCursor)).toBe('2024-07-15');
    planningView.set('week');
    shiftPlanningPeriod(-1);
    expect(get(planningCursor)).toBe('2024-07-08');
  });

  it('selectPlanningDay prefetches assignments for the picked date', async () => {
    apiMock.planning.getAssignments.mockResolvedValue({ date: '', goal_ids: [7] });
    selectPlanningDay('2024-06-20');
    expect(get(planningSelectedDay)).toBe('2024-06-20');
    await vi.waitFor(() =>
      expect(apiMock.planning.getAssignments).toHaveBeenCalledWith('2024-06-20')
    );
  });
});

describe('layer toggles + density', () => {
  it('every declared layer has a persisted default and toggles persist', () => {
    for (const layer of CALENDAR_LAYERS) {
      expect(DEFAULT_CALENDAR_LAYERS[layer]).toBeTypeOf('boolean');
    }
    // Tasks default on — they are the content of the calendar (#1660).
    expect(get(calendarLayers).tasks).toBe(true);
    toggleCalendarLayer('tasks');
    expect(get(calendarLayers).tasks).toBe(false);
    expect(patchUserSettingsMock).toHaveBeenCalledWith({
      calendarUi: { layers: { ...DEFAULT_CALENDAR_LAYERS, tasks: false } },
    });
  });

  it('setChipDensity persists and defines an overflow limit per level', () => {
    setChipDensity('compact');
    expect(get(chipDensity)).toBe('compact');
    expect(patchUserSettingsMock).toHaveBeenCalledWith({
      calendarUi: { density: 'compact' },
    });
    expect(CHIP_DENSITY_LIMITS.compact).toBeLessThan(CHIP_DENSITY_LIMITS.comfortable);
    expect(CHIP_DENSITY_LIMITS.full).toBe(Number.POSITIVE_INFINITY);
  });
});

describe('assignment data path', () => {
  it('loadAssignmentsForDate fetches every bucket key once and caches it', async () => {
    apiMock.planning.getAssignments.mockResolvedValue({ date: '', goal_ids: [1] });
    await loadAssignmentsForDate('2024-06-12');
    const called = apiMock.planning.getAssignments.mock.calls.length;
    expect(called).toBeGreaterThanOrEqual(4);
    await loadAssignmentsForDate('2024-06-12');
    expect(apiMock.planning.getAssignments.mock.calls.length).toBe(called);
    expect(get(planningAssignments)['2024-06-12']).toEqual([1]);
  });

  it('assignGoal normalizes by temporality and forwards the mirror flag', async () => {
    apiMock.planning.getAssignments.mockResolvedValue({ date: '', goal_ids: [] });
    const goal = { id: 9, temporality: 'WEEKLY' as const };
    await assignGoal(goal, '2024-06-12', true);
    expect(get(planningAssignments)['2024-06-10']).toEqual([9]);
    // No event sources cached for this bucket — undefined is forwarded.
    expect(apiMock.planning.setAssignments).toHaveBeenCalledWith('2024-06-10', [9], true, undefined);
  });

  it('unassignGoal removes the id from the normalized bucket', async () => {
    const goal = { id: 9, temporality: 'DAILY' as const };
    await assignGoal(goal, '2024-06-12');
    await unassignGoal(goal, '2024-06-12');
    expect(get(planningAssignments)['2024-06-12']).toEqual([]);
    // Assignments mirror into calendar_tasks by default now.
    expect(apiMock.planning.setAssignments).toHaveBeenLastCalledWith('2024-06-12', [], true, undefined);
  });
});
