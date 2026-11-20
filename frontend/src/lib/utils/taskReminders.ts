import type { CalendarTask } from '$lib/api';

/**
 * How long after a task's start a due reminder can still fire. A task hours
 * past its start is stale — surfacing a "starting soon" reminder for it on
 * page load would be noise, not signal.
 */
export const REMINDER_LATE_GRACE_MS = 60 * 60 * 1000;

const pad2 = (n: number): string => String(n).padStart(2, '0');

function localDayKey(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

/**
 * Today's undone tasks whose reminder window is open at `now` and that have
 * not been notified yet.
 *
 * A task is due when `now >= start - reminder_minutes`. The late-grace bound
 * keeps reminders from firing long after the start time has passed. Tasks
 * with a NULL date (unscheduled queue) or without start_time can never be
 * due — they carry reminder_minutes as inert metadata.
 */
export function dueTaskReminders(
  tasks: CalendarTask[],
  now: Date,
  notified: ReadonlySet<number>,
  lateGraceMs: number = REMINDER_LATE_GRACE_MS
): CalendarTask[] {
  const todayKey = localDayKey(now);
  return tasks.filter((task) => {
    if (task.done || notified.has(task.id)) return false;
    if (task.date !== todayKey || task.reminder_minutes === null || !task.start_time) return false;
    const [hh, mm] = task.start_time.slice(0, 5).split(':').map(Number);
    if (Number.isNaN(hh) || Number.isNaN(mm)) return false;
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hh, mm).getTime();
    return (
      now.getTime() >= start - task.reminder_minutes * 60_000 &&
      now.getTime() <= start + lateGraceMs
    );
  });
}

/**
 * Ask the browser for Notification permission. Must ONLY be called in
 * response to a user action (saving a reminder) — never on page load.
 * No-ops when notifications are unsupported or the answer is already known.
 */
export async function requestNotificationPermission(): Promise<void> {
  if (typeof Notification === 'undefined' || Notification.permission !== 'default') return;
  try {
    await Notification.requestPermission();
  } catch {
    // Rejected request (e.g. non-secure context) — toast-only reminders.
  }
}

/**
 * Fire a system notification for a task. Returns true when one was shown;
 * false (and silent) when the API is missing, permission was not granted,
 * or the constructor threw — the in-app toast is the always-on fallback.
 */
export function fireTaskNotification(title: string, body: string): boolean {
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return false;
  try {
    new Notification(title, { body });
    return true;
  } catch {
    return false;
  }
}
