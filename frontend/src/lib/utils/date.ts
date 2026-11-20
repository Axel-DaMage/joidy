import { getLocale } from '$lib/stores/locale';

/**
 * Parse a date-only `YYYY-MM-DD` string as a *local* date, anchored at local
 * noon so DST transitions can't roll it into an adjacent day. `new Date(s)`
 * treats bare date strings as UTC midnight, which renders/compares one day
 * early in UTC−N zones (#1306). Full datetimes pass through to `new Date`.
 */
export function parseLocalDate(s: string): Date {
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return new Date(`${s}T12:00:00`);
  return new Date(s);
}

/**
 * Local `YYYY-MM-DD` key for a Date. `d.toISOString().slice(0, 10)` returns
 * the *UTC* day, which drifts one day off the local date near midnight
 * (#1306) — day bucketing must use this instead.
 */
export function localDayKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function formatRelativeDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    if (diffHours === 0) {
      const diffMins = Math.floor(diffMs / (1000 * 60));
      if (diffMins === 0) return 'ahora';
      return `hace ${diffMins}m`;
    }
    return `hace ${diffHours}h`;
  }
  if (diffDays === 1) return 'ayer';
  if (diffDays < 7) return `hace ${diffDays}d`;

  return d.toLocaleDateString(getLocale(), { day: 'numeric', month: 'short' });
}

export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString(getLocale(), {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

export function formatTime(date: string | Date, use24Hour = true): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleTimeString(getLocale(), {
    hour: '2-digit',
    minute: '2-digit',
    hour12: !use24Hour,
  });
}

export function isToday(date: string | Date): boolean {
  const d = typeof date === 'string' ? new Date(date) : date;
  const today = new Date();
  return (
    d.getDate() === today.getDate() &&
    d.getMonth() === today.getMonth() &&
    d.getFullYear() === today.getFullYear()
  );
}

export function isThisWeek(date: string | Date): boolean {
  const d = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const weekStart = new Date(now);
  weekStart.setDate(now.getDate() - now.getDay());
  weekStart.setHours(0, 0, 0, 0);
  return d >= weekStart;
}

export function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

export function getMonthName(month: number): string {
  const months = [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
  ];
  return months[month];
}