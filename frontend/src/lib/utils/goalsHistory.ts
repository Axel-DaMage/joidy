import type { Goal } from '$lib/api';
import { localDayKey } from './date';

/**
 * Goals "Historial" tab feed model (#1669).
 *
 * Each goal contributes at most one feed entry, derived from its terminal
 * state (completed_at for COMPLETED, updated_at for FAILED/CANCELLED). The
 * feed is grouped chronologically (newest day first) so the heatmap can act
 * as a navigator that scrolls the agenda to a picked day.
 */

export type HistoryEventKind = 'COMPLETED' | 'FAILED' | 'CANCELLED';

export interface HistoryEvent {
  goal: Goal;
  kind: HistoryEventKind;
  /** Local YYYY-MM-DD day key. */
  date: string;
  /** Locale-formatted HH:MM, null when the timestamp can't be parsed. */
  time: string | null;
}

export interface HistoryDayGroup {
  date: string;
  items: HistoryEvent[];
}

export interface HistoryStats {
  completed: number;
  failed: number;
  cancelled: number;
  /** completed / (completed + failed) as a 0-100 integer, null when undecided. */
  effectiveness: number | null;
  /** Longest run of consecutive days with at least one completion. */
  bestStreak: number;
}

export function eventTime(iso: string): string | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

/** Day key `days` days before the local day `iso` (YYYY-MM-DD). */
export function daysBeforeKey(iso: string, days: number): string {
  const [y, m, d] = iso.split('-').map(Number);
  return localDayKey(new Date(y, m - 1, d - days + 1));
}

/** Day key of the day after `iso` (YYYY-MM-DD). */
export function nextDayKey(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  return localDayKey(new Date(y, m - 1, d + 1));
}

/** Flatten terminal-goal states into a newest-first chronological feed. */
export function buildHistoryEvents(goals: Goal[]): HistoryEvent[] {
  const events: HistoryEvent[] = [];
  for (const g of goals) {
    if ((g.state === 'COMPLETED' || g.is_completed) && g.completed_at) {
      events.push({
        goal: g,
        kind: 'COMPLETED',
        date: g.completed_at.split('T')[0],
        time: eventTime(g.completed_at),
      });
    } else if (g.state === 'FAILED' && g.updated_at) {
      events.push({
        goal: g,
        kind: 'FAILED',
        date: g.updated_at.split('T')[0],
        time: eventTime(g.updated_at),
      });
    } else if (g.state === 'CANCELLED' && g.updated_at) {
      events.push({
        goal: g,
        kind: 'CANCELLED',
        date: g.updated_at.split('T')[0],
        time: eventTime(g.updated_at),
      });
    }
  }
  // Order by the raw ISO source timestamp — `date`/`time` are display-only:
  // the locale-formatted time (e.g. "08:00 PM") does not sort chronologically.
  const sourceTs = (e: HistoryEvent): string =>
    (e.kind === 'COMPLETED' ? e.goal.completed_at : e.goal.updated_at) ?? '';
  events.sort(
    (a, b) => sourceTs(b).localeCompare(sourceTs(a)) || b.goal.id - a.goal.id
  );
  return events;
}

/**
 * Group a sorted feed into per-day agenda sections. Input must be sorted
 * newest-first so same-day events are adjacent.
 */
export function groupHistoryEvents(events: HistoryEvent[]): HistoryDayGroup[] {
  const groups: HistoryDayGroup[] = [];
  for (const e of events) {
    const last = groups[groups.length - 1];
    if (last && last.date === e.date) last.items.push(e);
    else groups.push({ date: e.date, items: [e] });
  }
  return groups;
}

/**
 * Per-period KPIs for the summary strip. `events` must be sorted
 * newest-first (see {@link buildHistoryEvents}).
 */
export function computeHistoryStats(events: HistoryEvent[]): HistoryStats {
  let completed = 0;
  let failed = 0;
  let cancelled = 0;
  // Distinct completion days in desc order — skip repeats of the previous day.
  const doneDaysDesc: string[] = [];
  let lastDone: string | null = null;
  for (const e of events) {
    if (e.kind === 'COMPLETED') {
      completed++;
      if (e.date !== lastDone) {
        doneDaysDesc.push(e.date);
        lastDone = e.date;
      }
    } else if (e.kind === 'FAILED') {
      failed++;
    } else {
      cancelled++;
    }
  }
  const decided = completed + failed;
  const effectiveness = decided > 0 ? Math.round((completed / decided) * 100) : null;
  // Desc order: a run continues while day+1 == previous day.
  let best = 0;
  let cur = 0;
  let prev: string | null = null;
  for (const day of doneDaysDesc) {
    cur = prev !== null && nextDayKey(day) === prev ? cur + 1 : 1;
    if (cur > best) best = cur;
    prev = day;
  }
  return { completed, failed, cancelled, effectiveness, bestStreak: best };
}
