/**
 * Shared types + pure helpers for the planning-suite calendar (#1658).
 * Kept framework-free so stores/tests can reuse them.
 */
import type {
  CalendarDayMetrics,
  CalendarEvent,
  CalendarTask,
  PlanSuggestion,
} from '$lib/api';
import { localDayKey } from '$lib/utils/date';

export type CalendarView = 'month' | 'week' | 'day' | 'agenda' | 'year';

export interface GridCell {
  day: number;
  inMonth: boolean;
  key: string;
}

/** One renderable row on a day: either a cached Google event or a joidy task. */
export type DayItem =
  | {
      kind: 'google';
      id: string;
      label: string;
      time: string | null;
      allDay: boolean;
      startMin: number | null;
      endMin: number | null;
      color: string | null;
      location: string | null;
      description: string | null;
      calendarId: string;
      htmlLink: string | null;
      event: CalendarEvent;
    }
  | {
      kind: 'task';
      id: string;
      label: string;
      time: string | null;
      allDay: boolean;
      startMin: number | null;
      endMin: number | null;
      color: string | null;
      location: string | null;
      description: string | null;
      task: CalendarTask;
    };

export interface CalendarPrefs {
  view: CalendarView;
  heatmap: boolean;
  showMetrics: boolean;
  hiddenCalendarIds: string[];
  trayCollapsed: boolean;
}

const PREFS_KEY = 'joidy-calendar-prefs';
const VALID_VIEWS: CalendarView[] = ['month', 'week', 'day', 'agenda', 'year'];

export function loadCalendarPrefs(): CalendarPrefs {
  const fallback: CalendarPrefs = {
    view: 'month',
    heatmap: false,
    showMetrics: true,
    hiddenCalendarIds: [],
    trayCollapsed: false,
  };
  if (typeof localStorage === 'undefined') return fallback;
  try {
    const raw = localStorage.getItem(PREFS_KEY);
    // Migrate the legacy single-key view preference (#1235 → #1658) plus the
    // namespaced #1673 keys (`joidy.calendar.*`, JSON-encoded) written by the
    // pre-suite page so upgrading users keep their view/tray prefs.
    const jsonPref = (key: string): unknown => {
      const v = localStorage.getItem(key);
      if (v === null) return null;
      try {
        return JSON.parse(v) as unknown;
      } catch {
        return null;
      }
    };
    const namespacedView = jsonPref('joidy.calendar.view');
    const legacyView =
      (typeof namespacedView === 'string' ? namespacedView : null) ??
      localStorage.getItem('joidy-calendar-view');
    const namespacedTray = jsonPref('joidy.calendar.trayCollapsed');
    const legacyTray =
      namespacedTray === true || localStorage.getItem('joidy-calendar-tray-collapsed') === '1';
    const parsed = raw ? (JSON.parse(raw) as Partial<CalendarPrefs>) : {};
    return {
      view:
        parsed.view && VALID_VIEWS.includes(parsed.view)
          ? parsed.view
          : legacyView && VALID_VIEWS.includes(legacyView as CalendarView)
            ? (legacyView as CalendarView)
            : 'month',
      heatmap: parsed.heatmap ?? false,
      showMetrics: parsed.showMetrics ?? true,
      hiddenCalendarIds: Array.isArray(parsed.hiddenCalendarIds)
        ? parsed.hiddenCalendarIds.filter((id): id is string => typeof id === 'string')
        : [],
      trayCollapsed: parsed.trayCollapsed ?? legacyTray,
    };
  } catch {
    return fallback;
  }
}

export function saveCalendarPrefs(prefs: CalendarPrefs): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
}

/** Bucket a cached Google event into its local-day key. */
export function eventDayKey(event: CalendarEvent): string {
  // All-day events are cached as UTC midnight (`YYYY-MM-DDT00:00:00Z`);
  // passing that through Date shifts them onto the previous day in
  // negative-offset zones. Bucket them by the raw date prefix instead.
  if (event.all_day) return event.start_at.slice(0, 10);
  return localDayKey(new Date(event.start_at));
}

export function minutesOf(d: Date): number {
  return d.getHours() * 60 + d.getMinutes();
}

/** `HH:MM[:SS]` → minutes since midnight. */
export function hhmmToMinutes(hhmm: string | null | undefined): number | null {
  if (!hhmm) return null;
  const [h, m] = hhmm.split(':').map(Number);
  if (Number.isNaN(h) || Number.isNaN(m)) return null;
  return h * 60 + m;
}

/**
 * Merge Google events + joidy tasks into per-day item lists, sorted by start
 * time. A task mirrored to Google (google_event_id) renders as the editable
 * task chip only — its cached read-only copy is filtered out so it does not
 * appear twice.
 */
export function buildItemsByDay(
  events: CalendarEvent[],
  tasks: CalendarTask[],
  opts: {
    hiddenCalendarIds?: Set<string>;
    calendarColors?: Map<string, string>;
    dtFormatter: Intl.DateTimeFormat;
    query?: string;
  }
): Map<string, DayItem[]> {
  const { hiddenCalendarIds, calendarColors, dtFormatter } = opts;
  const query = (opts.query ?? '').trim().toLowerCase();
  const mirrored = new Set(
    tasks.map((t) => t.google_event_id).filter((id): id is string => id !== null)
  );

  const matches = (text: string | null | undefined): boolean =>
    query === '' || (text ?? '').toLowerCase().includes(query);

  const byDay = new Map<string, DayItem[]>();
  for (const ev of events) {
    if (mirrored.has(ev.google_id)) continue;
    if (hiddenCalendarIds?.has(ev.calendar_id)) continue;
    if (query && !matches(ev.summary) && !matches(ev.location) && !matches(ev.description))
      continue;
    const key = eventDayKey(ev);
    const start = new Date(ev.start_at);
    const end = ev.end_at ? new Date(ev.end_at) : null;
    const item: DayItem = {
      kind: 'google',
      id: ev.google_id,
      label: ev.summary || '—',
      time: ev.all_day ? null : dtFormatter.format(start),
      allDay: ev.all_day,
      startMin: ev.all_day ? null : minutesOf(start),
      endMin: ev.all_day || !end ? null : minutesOf(end),
      color: calendarColors?.get(ev.calendar_id) ?? null,
      location: ev.location,
      description: ev.description,
      calendarId: ev.calendar_id,
      htmlLink: ev.html_link,
      event: ev,
    };
    const list = byDay.get(key) ?? [];
    list.push(item);
    byDay.set(key, list);
  }
  for (const task of tasks) {
    if (task.date === null) continue;
    if (
      query &&
      !matches(task.title) &&
      !matches(task.location) &&
      !matches(task.description)
    )
      continue;
    const item: DayItem = {
      kind: 'task',
      id: `t-${task.id}`,
      label: task.title,
      time: task.start_time ? task.start_time.slice(0, 5) : null,
      allDay: task.start_time === null,
      startMin: hhmmToMinutes(task.start_time),
      endMin: hhmmToMinutes(task.end_time),
      color: task.color,
      location: task.location,
      description: task.description,
      task,
    };
    const list = byDay.get(task.date) ?? [];
    list.push(item);
    byDay.set(task.date, list);
  }
  for (const list of byDay.values()) {
    list.sort((a, b) => {
      if (a.allDay !== b.allDay) return a.allDay ? -1 : 1;
      return (a.startMin ?? 9999) - (b.startMin ?? 9999);
    });
  }
  return byDay;
}

/** Index a day-metrics array into a {dayKey: metrics} map. */
export function metricsByDay(metrics: CalendarDayMetrics[]): Map<string, CalendarDayMetrics> {
  return new Map(metrics.map((m) => [m.date, m]));
}

/**
 * Productivity density score for the heatmap overlay (#1658): a weighted mix
 * of focus minutes, XP and notes, roughly normalized so a "solid" day lands
 * near 1.0 (≈2h focus or ~150 XP of activity).
 */
export function densityScore(m: CalendarDayMetrics | undefined): number {
  if (!m) return 0;
  const raw = m.focus_minutes / 120 + m.xp / 150 + m.notes / 8 + m.goals_completed / 3;
  return Math.min(1, raw / 2);
}

/** Monday-first 6×7 grid covering `year`/`month` (0-based month). */
export function monthCells(year: number, month: number): GridCell[] {
  const first = new Date(year, month, 1);
  const offset = (first.getDay() + 6) % 7; // Monday = 0
  const start = new Date(year, month, 1 - offset);
  const cells: GridCell[] = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
    cells.push({ day: d.getDate(), inMonth: d.getMonth() === month, key: localDayKey(d) });
  }
  return cells;
}

/** Cells of the mini-month navigator: leading/trailing days are blanks. */
export function miniMonthCells(year: number, month: number): (GridCell | null)[] {
  const first = new Date(year, month, 1);
  const offset = (first.getDay() + 6) % 7;
  const dim = new Date(year, month + 1, 0).getDate();
  const cells: (GridCell | null)[] = Array.from({ length: offset }, () => null);
  for (let d = 1; d <= dim; d++) {
    cells.push({ day: d, inMonth: true, key: localDayKey(new Date(year, month, d)) });
  }
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

/** 7 Monday-first day keys for the week containing `anchorKey` (YYYY-MM-DD). */
export function weekDayKeys(anchorKey: string): string[] {
  const anchor = new Date(`${anchorKey}T12:00:00`);
  const monday = new Date(
    anchor.getFullYear(),
    anchor.getMonth(),
    anchor.getDate() - ((anchor.getDay() + 6) % 7)
  );
  return Array.from({ length: 7 }, (_, i) =>
    localDayKey(new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i))
  );
}

export function addDays(dayKey: string, days: number): string {
  // Anchor at local noon so adding days across a DST transition stays stable.
  const d = new Date(`${dayKey}T12:00:00`);
  d.setDate(d.getDate() + days);
  return localDayKey(d);
}

export function planSuggestionsByDay(
  suggestions: PlanSuggestion[]
): Map<string, PlanSuggestion[]> {
  const map = new Map<string, PlanSuggestion[]>();
  for (const s of suggestions) {
    const list = map.get(s.date) ?? [];
    list.push(s);
    map.set(s.date, list);
  }
  return map;
}

/** Mood score → a compact emoji badge for day cells. */
export function moodGlyph(score: number | null | undefined): string {
  if (!score) return '';
  return ['', '😞', '😕', '😐', '🙂', '😄'][Math.max(1, Math.min(5, score))];
}
