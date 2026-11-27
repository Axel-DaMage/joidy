// Shared planning-calendar state (#1660). One store backs every calendar
// surface — the Goals → Planificación tab and /calendar — so cursor date,
// view mode, the planning-assignment cache and the per-layer visibility
// toggles live in a single place and neither page re-implements the same
// fetch/render state.
//
// Persistence: view mode, layer visibility and chip density are stored under
// `calendarUi` in the shared user-settings blob (`joidy-user-settings-v1`).
// Hydration falls back to the legacy per-page keys (`joidy-calendar-view`,
// `goals.planningView`) so previously saved view prefs keep working.

import { get, writable } from 'svelte/store';
import { browser } from '$app/env';
import { api, type Goal } from '$lib/api';
import { localDayKey, parseLocalDate } from '$lib/utils/date';
import { loadUserSettings, patchUserSettings } from '$lib/utils/userSettings';
import { logger } from '$lib/utils/logger';

// ── Types ───────────────────────────────────────────────────────────────────

export type PlanningCalendarView = 'month' | 'week' | 'agenda';

export const PLAN_TEMPS = ['DAILY', 'WEEKLY', 'MONTHLY', 'ANNUAL', 'ONEOFF'] as const;
export type PlanningTemporality = (typeof PLAN_TEMPS)[number];

export interface CalendarLayerVisibility {
  /** Goal planning assignments (PlanningAssignment ↔ goal links). */
  planning: boolean;
  /** Local calendar_tasks — the real calendar content, on by default. */
  tasks: boolean;
  /** Read-only Google Calendar events from the sync cache. */
  google: boolean;
  /** Personal-streak check-in state, rendered as day-cell badges. */
  streaks: boolean;
  /** Notes created on each day, rendered as a count badge. */
  notes: boolean;
}

export type CalendarLayer = keyof CalendarLayerVisibility;
export const CALENDAR_LAYERS: CalendarLayer[] = [
  'planning',
  'tasks',
  'google',
  'streaks',
  'notes',
];

/** Per the #1660 streaks/tasks decision: tasks and google events default on,
 * planning on (it IS the planning calendar), streaks/notes opt-in badges. */
export const DEFAULT_CALENDAR_LAYERS: CalendarLayerVisibility = {
  planning: true,
  tasks: true,
  google: true,
  streaks: false,
  notes: false,
};

export type ChipDensity = 'compact' | 'comfortable' | 'full';
export const CHIP_DENSITY_ORDER: ChipDensity[] = ['compact', 'comfortable', 'full'];
/** Max chips rendered inside a month day cell before the "+N more" overflow. */
export const CHIP_DENSITY_LIMITS: Record<ChipDensity, number> = {
  compact: 2,
  comfortable: 5,
  full: Number.POSITIVE_INFINITY,
};

export const AGENDA_DAY_COUNT = 14;

// ── Pure grid helpers ───────────────────────────────────────────────────────

/**
 * Bucket a day-level date into the normalized key a goal's temporality
 * assigns to: DAILY keeps the day, WEEKLY → its Monday, MONTHLY → the 1st,
 * ANNUAL → Jan 1st. ONEOFF has no period bucket — it stays a day key.
 */
export function getNormalizedDate(
  date: string,
  temporality: PlanningTemporality | string
): string {
  if (!date) return date;
  const d = parseLocalDate(date);
  if (temporality === 'WEEKLY') {
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(d.setDate(diff));
    return localDayKey(monday);
  }
  if (temporality === 'MONTHLY') return date.substring(0, 7) + '-01';
  if (temporality === 'ANNUAL') return date.substring(0, 4) + '-01-01';
  return date;
}

/** 42 Monday-first cells covering the month that contains `cursor`. */
export function monthCellsFor(cursor: string): { iso: string; day: number; inMonth: boolean }[] {
  const d = parseLocalDate(cursor);
  const y = d.getFullYear();
  const m = d.getMonth();
  const offset = (new Date(y, m, 1).getDay() + 6) % 7; // Monday start
  const start = new Date(y, m, 1 - offset);
  return Array.from({ length: 42 }, (_, i) => {
    const cell = new Date(start);
    cell.setDate(start.getDate() + i);
    return { iso: localDayKey(cell), day: cell.getDate(), inMonth: cell.getMonth() === m };
  });
}

/** The 7 ISO day keys (Monday-first) of the week containing `cursor`. */
export function weekDaysFor(cursor: string): string[] {
  const monday = parseLocalDate(getNormalizedDate(cursor, 'WEEKLY'));
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return localDayKey(d);
  });
}

/** `count` consecutive ISO day keys starting at `cursor` (agenda view). */
export function agendaDaysFor(cursor: string, count = AGENDA_DAY_COUNT): string[] {
  const start = parseLocalDate(cursor);
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return localDayKey(d);
  });
}

/**
 * Union of every normalized-bucket key a date belongs to (its day, week,
 * month, year) — the full set of keys an assignment fetch/render must cover.
 */
export function normalizedKeysForDate(date: string): string[] {
  const keys = new Set<string>();
  for (const temp of PLAN_TEMPS) keys.add(getNormalizedDate(date, temp));
  return [...keys];
}

/**
 * Union of goal ids assigned to any period a date belongs to — deduplicated.
 */
export function assignedIdsForDate(
  assignmentsMap: Record<string, number[]>,
  date: string
): number[] {
  const ids = new Set<number>();
  for (const temp of PLAN_TEMPS) {
    for (const id of assignmentsMap[getNormalizedDate(date, temp)] || []) ids.add(id);
  }
  return [...ids];
}

// ── Shared state ────────────────────────────────────────────────────────────

/** Cursor date (YYYY-MM-DD) anchoring the visible month/week/agenda period. */
export const planningCursor = writable<string>(localDayKey(new Date()));

/** Shared view mode; 'agenda' is only offered by /calendar — the goals
 * planning tab coerces it back to 'month'. */
export const planningView = writable<PlanningCalendarView>('month');

/** Currently selected day (YYYY-MM-DD); null = no selection. */
export const planningSelectedDay = writable<string | null>(null);

/** Planning-assignment cache: normalized date key → assigned goal ids. */
export const planningAssignments = writable<Record<string, number[]>>({});

export const calendarLayers = writable<CalendarLayerVisibility>({
  ...DEFAULT_CALENDAR_LAYERS,
});

export const chipDensity = writable<ChipDensity>('comfortable');

// Hydrate persisted prefs once (browser only — SSR/tests get defaults).
if (browser) {
  try {
    const ui = loadUserSettings().calendarUi;
    if (ui?.view === 'month' || ui?.view === 'week' || ui?.view === 'agenda') {
      planningView.set(ui.view);
    } else {
      const legacy =
        localStorage.getItem('joidy-calendar-view') ??
        localStorage.getItem('goals.planningView');
      if (legacy === 'month' || legacy === 'week' || legacy === 'agenda') {
        planningView.set(legacy);
      }
    }
    if (ui?.layers) {
      calendarLayers.set({ ...DEFAULT_CALENDAR_LAYERS, ...ui.layers });
    }
    if (
      ui?.density === 'compact' ||
      ui?.density === 'comfortable' ||
      ui?.density === 'full'
    ) {
      chipDensity.set(ui.density);
    }
  } catch {
    // Storage errors fall back to defaults.
  }
}

// ── Actions ─────────────────────────────────────────────────────────────────

export function setPlanningView(next: PlanningCalendarView): void {
  planningView.set(next);
  patchUserSettings({ calendarUi: { view: next } });
}

export function shiftPlanningPeriod(dir: 1 | -1): void {
  const view = get(planningView);
  const d = parseLocalDate(get(planningCursor));
  if (view === 'week') d.setDate(d.getDate() + 7 * dir);
  else if (view === 'agenda') d.setDate(d.getDate() + 7 * dir);
  else d.setMonth(d.getMonth() + dir);
  planningCursor.set(localDayKey(d));
}

/** Move cursor + selection back to today. */
export function goPlanningToday(): void {
  const today = localDayKey(new Date());
  planningCursor.set(today);
  selectPlanningDay(today);
}

/** Select a day (without moving the cursor period). Triggers a lazy
 * assignment load so the selection detail is fresh on every surface. */
export function selectPlanningDay(iso: string | null): void {
  planningSelectedDay.set(iso);
  if (iso) {
    loadAssignmentsForDate(iso).catch((e) =>
      logger.error('[planningCalendar] selection prefetch failed:', e)
    );
  }
}

/** Select a day AND move the cursor period to it (deep-jumps from other
 * surfaces, e.g. the goals agenda rail). */
export function jumpToPlanningDay(iso: string): void {
  planningCursor.set(iso);
  selectPlanningDay(iso);
}

export function toggleCalendarLayer(layer: CalendarLayer): void {
  calendarLayers.update((current) => {
    const next = { ...current, [layer]: !current[layer] };
    patchUserSettings({ calendarUi: { layers: next } });
    return next;
  });
}

export function setChipDensity(next: ChipDensity): void {
  chipDensity.set(next);
  patchUserSettings({ calendarUi: { density: next } });
}

// ── Assignment data path ────────────────────────────────────────────────────

/** Fetch the assignments of one date (all its normalized buckets) into the
 * shared cache. Missing/failed keys land as empty lists so failed reads
 * don't wedge the cache in a permanent "not loaded" state. */
export async function loadAssignmentsForDate(date: string): Promise<void> {
  if (!date) return;
  const map = get(planningAssignments);
  const keys = normalizedKeysForDate(date).filter((k) => !(k in map));
  if (keys.length === 0) return;
  const results = await Promise.all(
    keys.map(async (d) => {
      try {
        const res = await api.planning.getAssignments(d);
        return { date: d, ids: res.goal_ids };
      } catch {
        return { date: d, ids: [] as number[] };
      }
    })
  );
  planningAssignments.update((m) => ({
    ...m,
    ...Object.fromEntries(results.map((r) => [r.date, r.ids])),
  }));
}

/** Bulk-prefetch every normalized key the given dates touch — used to cover
 * the whole visible grid in one pass so day cells render without waiting. */
export async function loadAssignmentsForRange(dates: string[]): Promise<void> {
  const map = get(planningAssignments);
  const keys = new Set<string>();
  for (const date of dates) {
    if (!date) continue;
    for (const k of normalizedKeysForDate(date)) keys.add(k);
  }
  const missing = [...keys].filter((k) => !(k in map));
  if (missing.length === 0) return;
  const results = await Promise.all(
    missing.map(async (d) => {
      try {
        const res = await api.planning.getAssignments(d);
        return { date: d, ids: res.goal_ids };
      } catch {
        return { date: d, ids: [] as number[] };
      }
    })
  );
  planningAssignments.update((m) => ({
    ...m,
    ...Object.fromEntries(results.map((r) => [r.date, r.ids])),
  }));
}

/** Drop the cached assignments — callers re-run their range prefetch so the
 * next paint reflects the server truth. */
export function invalidatePlanningAssignments(): void {
  planningAssignments.set({});
}

type AssignableGoal = Pick<Goal, 'id' | 'temporality'>;

/** Optimistically assign `goal` to `date` (normalized by its temporality)
 * and persist through the planning API. `mirrorToCalendar` forwards the
 * `create_calendar_task` flag — the PlanningAssignment ↔ calendar_tasks
 * mirror is unchanged (#1234). */
export async function assignGoal(
  goal: AssignableGoal,
  date: string,
  mirrorToCalendar = false
): Promise<void> {
  if (!date) return;
  const normDate = getNormalizedDate(date, goal.temporality);
  planningAssignments.update((m) => {
    const next = { ...m };
    const list = [...(next[normDate] ?? [])];
    if (!list.includes(goal.id)) list.push(goal.id);
    next[normDate] = list;
    return next;
  });
  try {
    await api.planning.setAssignments(
      normDate,
      get(planningAssignments)[normDate],
      mirrorToCalendar
    );
  } catch (e) {
    logger.error('Error saving assignment:', e);
  }
}

export async function unassignGoal(
  goal: AssignableGoal,
  date: string,
  mirrorToCalendar = false
): Promise<void> {
  if (!date) return;
  const normDate = getNormalizedDate(date, goal.temporality);
  planningAssignments.update((m) => {
    if (!m[normDate]) return m;
    return { ...m, [normDate]: m[normDate].filter((id) => id !== goal.id) };
  });
  try {
    await api.planning.setAssignments(
      normDate,
      get(planningAssignments)[normDate] ?? [],
      mirrorToCalendar
    );
  } catch (e) {
    logger.error('Error saving assignment removal:', e);
  }
}
