<script lang="ts">
  import { onMount } from 'svelte';
  import {
    api,
    type CalendarEvent,
    type CalendarTask,
    type CalendarTaskPriority,
    type CalendarTaskRecurrence,
    type PlanSuggestion,
  } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import { parseLocalDate } from '$lib/utils/date';
  import { showNotification } from '$lib/stores/notifications';
  import {
    dueTaskReminders,
    fireTaskNotification,
    requestNotificationPermission,
  } from '$lib/utils/taskReminders';
  import ChevronLeft from 'lucide-svelte/icons/chevron-left';
  import ChevronRight from 'lucide-svelte/icons/chevron-right';
  import ChevronDown from 'lucide-svelte/icons/chevron-down';
  import CalendarDays from 'lucide-svelte/icons/calendar-days';
  import Inbox from 'lucide-svelte/icons/inbox';
  import RefreshCw from 'lucide-svelte/icons/refresh-cw';
  import Settings from 'lucide-svelte/icons/settings';
  import Lock from 'lucide-svelte/icons/lock';
  import Plus from 'lucide-svelte/icons/plus';
  import Trash2 from 'lucide-svelte/icons/trash-2';
  import Pencil from 'lucide-svelte/icons/pencil';
  import X from 'lucide-svelte/icons/x';
  import Check from 'lucide-svelte/icons/check';
  import Repeat from 'lucide-svelte/icons/repeat';
  import Sparkles from 'lucide-svelte/icons/sparkles';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { t } from 'svelte-i18n';

  interface CalendarStatus {
    connected: boolean;
    calendars: number;
    cached_events: number;
    last_synced_at: string | null;
  }

  type DayItem =
    | {
        kind: 'google';
        id: string;
        time: string | null;
        label: string;
        location?: string | null;
        allDay: boolean;
      }
    | { kind: 'task'; time: string | null; label: string; task: CalendarTask };

  const PRIORITIES: CalendarTaskPriority[] = ['LOW', 'MEDIUM', 'HIGH', 'URGENT'];

  // Recurrence + reminder pickers (#1238). `null` minutes = no reminder.
  const RECURRENCE_OPTIONS: { value: CalendarTaskRecurrence; labelKey: string }[] = [
    { value: 'NONE', labelKey: 'recurrenceNone' },
    { value: 'DAILY', labelKey: 'recurrenceDaily' },
    { value: 'WEEKLY', labelKey: 'recurrenceWeekly' },
    { value: 'MONTHLY', labelKey: 'recurrenceMonthly' },
  ];
  const REMINDER_OPTIONS: { minutes: number | null; labelKey: string }[] = [
    { minutes: null, labelKey: 'reminderNone' },
    { minutes: 5, labelKey: 'reminderMin5' },
    { minutes: 15, labelKey: 'reminderMin15' },
    { minutes: 30, labelKey: 'reminderMin30' },
    { minutes: 60, labelKey: 'reminderMin60' },
  ];

  let events: CalendarEvent[] = $state([]);
  let tasks: CalendarTask[] = $state([]);
  let status: CalendarStatus | null = $state(null);
  let loading = $state(true);
  let loadError = $state(false);
  let syncing = $state(false);

  type CalendarView = 'month' | 'week' | 'agenda';
  let currentView = $state<CalendarView>(
    (typeof localStorage !== 'undefined' &&
      (localStorage.getItem('joidy-calendar-view') as CalendarView)) ||
      'month'
  );
  let weekOffset = $state(0);

  function setView(view: CalendarView): void {
    currentView = view;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('joidy-calendar-view', view);
    }
  }

  let viewYear = $state(new Date().getFullYear());
  let viewMonth = $state(new Date().getMonth()); // 0-based
  let selectedDay = $state<string | null>(null);

  // Quick-add state
  let quickAddTitle = $state('');
  let quickAddTime = $state('');
  let quickAddPriority = $state<CalendarTaskPriority>('MEDIUM');
  let quickAddRecurrence = $state<CalendarTaskRecurrence>('NONE');
  let quickAddReminder = $state<number | null>(null);
  let publishToGoogle = $state(false);
  let addingTask = $state(false);

  // Inline edit state
  let editingTaskId = $state<number | null>(null);
  let editTitle = $state('');
  let editTime = $state('');
  let editEndTime = $state('');
  let editRecurrence = $state<CalendarTaskRecurrence>('NONE');
  let editReminder = $state<number | null>(null);

  // Tasks already reminded this page session (#1238) — plain Set is fine,
  // it only feeds the polling interval, not the template.
  const notifiedTaskIds = new Set<number>();

  const dtFormatter = new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  });

  const pad2 = (n: number): string => String(n).padStart(2, '0');

  function localDayKey(d: Date): string {
    return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
  }

  function currentDayKey(): string {
    return localDayKey(new Date());
  }

  // The browser's IANA zone, sent with `dateTime` payloads so Google anchors
  // naive local times to the right zone (Google EventDateTime.timeZone).
  const localTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  function eventDay(event: CalendarEvent): string {
    // All-day events are cached as UTC midnight (`YYYY-MM-DDT00:00:00Z`);
    // passing that through Date shifts them onto the previous day in
    // negative-offset zones. Bucket them by the raw date prefix instead.
    if (event.all_day) return event.start_at.slice(0, 10);
    return localDayKey(new Date(event.start_at));
  }

  function taskDay(task: CalendarTask): string | null {
    return task.date;
  }

  let todayKey = $state(currentDayKey());

  // Re-derive "today" after a midnight rollover (#1306). A selection pinned
  // to the old "today" follows the new day; explicit picks are left alone.
  // Returns true when the day actually changed.
  function syncToday(): boolean {
    const next = currentDayKey();
    if (next === todayKey) return false;
    const prev = todayKey;
    todayKey = next;
    if (selectedDay === prev) selectedDay = next;
    return true;
  }

  // Grid cells (Monday-first): 6 weeks × 7 days, with in-month flags.
  let gridCells = $derived.by(() => {
    const first = new Date(viewYear, viewMonth, 1);
    const offset = (first.getDay() + 6) % 7; // Monday = 0
    const cells: { day: number; inMonth: boolean; key: string }[] = [];
    const start = new Date(viewYear, viewMonth, 1 - offset);
    for (let i = 0; i < 42; i++) {
      const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
      cells.push({
        day: d.getDate(),
        inMonth: d.getMonth() === viewMonth,
        key: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`,
      });
    }
    return cells;
  });

  let monthEvents = $derived.by(() => {
    const byDay = new Map<string, CalendarEvent[]>();
    for (const ev of events) {
      const key = eventDay(ev);
      if (!byDay.has(key)) byDay.set(key, []);
      byDay.get(key)!.push(ev);
    }
    for (const list of byDay.values()) {
      list.sort((a, b) => a.start_at.localeCompare(b.start_at));
    }
    return byDay;
  });

  let monthTasks = $derived.by(() => {
    const byDay = new Map<string, CalendarTask[]>();
    for (const task of tasks) {
      const key = taskDay(task);
      // NULL date → lives in the unscheduled tray, not on a day cell (#1234).
      if (key === null) continue;
      if (!byDay.has(key)) byDay.set(key, []);
      byDay.get(key)!.push(task);
    }
    for (const list of byDay.values()) {
      list.sort((a, b) => {
        const at = a.start_time ?? '99';
        const bt = b.start_time ?? '99';
        if (at !== bt) return at.localeCompare(bt);
        return a.id - b.id;
      });
    }
    return byDay;
  });

  let monthItems = $derived.by(() => {
    const byDay = new Map<string, DayItem[]>();
    // A task mirrored to Google (google_event_id) renders as the editable
    // task chip only — skip its cached read-only Google copy so it doesn't
    // appear twice on the same day.
    const mirroredGoogleIds = new Set(
      tasks.map((t) => t.google_event_id).filter((id): id is string => id !== null)
    );
    for (const [key, evts] of monthEvents) {
      const visible = evts.filter((ev) => !mirroredGoogleIds.has(ev.google_id));
      if (visible.length === 0) continue;
      byDay.set(
        key,
        visible.map((ev) => ({
          kind: 'google' as const,
          id: ev.google_id,
          time: ev.all_day ? null : dtFormatter.format(new Date(ev.start_at)),
          label: ev.summary || '—',
          location: ev.location,
          allDay: ev.all_day,
        }))
      );
    }
    for (const [key, dayTasks] of monthTasks) {
      const list = byDay.get(key) ?? [];
      for (const task of dayTasks) {
        list.push({
          kind: 'task' as const,
          time: task.start_time ? task.start_time.slice(0, 5) : null,
          label: task.title,
          task,
        });
      }
      byDay.set(key, list);
    }
    for (const list of byDay.values()) {
      list.sort((a, b) => (a.time ?? '99:99').localeCompare(b.time ?? '99:99'));
    }
    return byDay;
  });

  let selectedDayItems = $derived(selectedDay ? (monthItems.get(selectedDay) ?? []) : []);

  // Unscheduled queue ("sin planificar", #1234): tasks with no date.
  let unscheduledTasks = $derived(
    tasks.filter((t) => t.date === null).sort((a, b) => a.created_at.localeCompare(b.created_at))
  );
  let trayCollapsed = $state(
    typeof localStorage !== 'undefined' &&
      localStorage.getItem('joidy-calendar-tray-collapsed') === '1'
  );
  let trayAddTitle = $state('');
  let trayAdding = $state(false);

  function toggleTray(): void {
    trayCollapsed = !trayCollapsed;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('joidy-calendar-tray-collapsed', trayCollapsed ? '1' : '0');
    }
  }

  // Week view: 7 days based on current weekOffset. Anchored to `todayKey`
  // (not `new Date()`) so the derived recomputes on midnight rollover.
  let weekDays = $derived.by(() => {
    const today = parseLocalDate(todayKey);
    const dayOfWeek = (today.getDay() + 6) % 7; // Monday = 0
    const monday = new Date(
      today.getFullYear(),
      today.getMonth(),
      today.getDate() - dayOfWeek + weekOffset * 7
    );
    const days: { day: number; key: string; weekdayIndex: number; monthName: string }[] = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      days.push({
        day: d.getDate(),
        key,
        weekdayIndex: i,
        monthName: $t(`calendar.months.${d.getMonth()}`),
      });
    }
    return days;
  });

  let weekLabel = $derived.by(() => {
    if (weekDays.length === 0) return '';
    const first = weekDays[0];
    const last = weekDays[6];
    // Year comes from the week itself: `viewYear` tracks month navigation,
    // which week navigation (weekOffset) never touches.
    const firstYear = first.key.slice(0, 4);
    const lastYear = last.key.slice(0, 4);
    if (first.monthName === last.monthName) {
      return `${first.day} - ${last.day} ${first.monthName} ${firstYear}`;
    }
    const firstPart =
      firstYear !== lastYear
        ? `${first.day} ${first.monthName} ${firstYear}`
        : `${first.day} ${first.monthName}`;
    return `${firstPart} - ${last.day} ${last.monthName} ${lastYear}`;
  });

  // Agenda view: Next 14 days starting from today (or selectedDay if set)
  let agendaDays = $derived.by(() => {
    const start = parseLocalDate(todayKey);
    const days: { date: Date; key: string; items: DayItem[] }[] = [];
    for (let i = 0; i < 14; i++) {
      const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      const items = monthItems.get(key) ?? [];
      days.push({ date: d, key, items });
    }
    return days;
  });

  // Union of every view's visible day range — bounds the cached-events and
  // task fetches so we never pull the whole table. Keys are YYYY-MM-DD
  // strings, so lexicographic compare orders them.
  let fetchRange = $derived.by(() => {
    const firsts = [gridCells[0]?.key, weekDays[0]?.key, agendaDays[0]?.key].filter(
      (k): k is string => k !== undefined
    );
    const lasts = [
      gridCells[gridCells.length - 1]?.key,
      weekDays[weekDays.length - 1]?.key,
      agendaDays[agendaDays.length - 1]?.key,
    ].filter((k): k is string => k !== undefined);
    return {
      start: firsts.reduce((a, b) => (b < a ? b : a)),
      end: lasts.reduce((a, b) => (b > a ? b : a)),
    };
  });

  function prevRange(): void {
    if (currentView === 'week') {
      weekOffset -= 1;
    } else {
      if (viewMonth === 0) {
        viewYear -= 1;
        viewMonth = 11;
      } else {
        viewMonth -= 1;
      }
    }
    void refresh();
  }

  function nextRange(): void {
    if (currentView === 'week') {
      weekOffset += 1;
    } else {
      if (viewMonth === 11) {
        viewYear += 1;
        viewMonth = 0;
      } else {
        viewMonth += 1;
      }
    }
    void refresh();
  }

  function goToday(): void {
    viewYear = new Date().getFullYear();
    viewMonth = new Date().getMonth();
    weekOffset = 0;
    todayKey = currentDayKey();
    selectedDay = todayKey;
    void refresh();
  }

  function eventTime(ev: CalendarEvent): string {
    if (ev.all_day) return $t('calendar.allDay');
    return dtFormatter.format(new Date(ev.start_at));
  }

  async function refresh(): Promise<void> {
    try {
      syncToday();
      // The cache stores all-day events at UTC midnight, which in
      // negative-offset zones is an instant on the previous local day —
      // pad the lower bound by one day so those rows are still returned.
      const eventsStart = new Date(`${addDays(fetchRange.start, -1)}T00:00:00`).toISOString();
      const eventsEnd = new Date(`${fetchRange.end}T23:59:59.999`).toISOString();
      const [evts, st, scheduled, unscheduled] = await Promise.all([
        api.google.calendarEvents({ start: eventsStart, end: eventsEnd }),
        api.google.calendarStatus(),
        api.calendarTasks.list({ start: fetchRange.start, end: fetchRange.end }),
        api.calendarTasks.list({ unscheduled: true }),
      ]);
      events = evts;
      status = st;
      tasks = [...scheduled, ...unscheduled];
      loadError = false;
    } catch (e) {
      logger.error(e);
      // Surface the failure — the old log-only path rendered an empty
      // calendar indistinguishable from "no events". When stale data is
      // already on screen a toast is enough; only swap to the error state
      // when there is nothing to show (#1305).
      if (events.length === 0 && tasks.length === 0) {
        loadError = true;
      } else {
        showNotification($t('calendar.loadError'), 'error');
      }
    } finally {
      loading = false;
    }
  }

  // Auto-sync staleness threshold: sync on page entry if the last sync is
  // older than this (or never happened).
  const AUTO_SYNC_STALE_MS = 15 * 60 * 1000;

  async function sync(silent = false): Promise<void> {
    syncing = true;
    try {
      await api.google.calendarSync();
      if (!silent) showNotification($t('calendar.syncOk'), 'success');
      await refresh();
    } catch (e) {
      logger.error(e);
      if (!silent) showNotification($t('calendar.syncError'), 'error');
    } finally {
      syncing = false;
    }
  }

  async function maybeAutoSync(): Promise<void> {
    if (!status?.connected) return;
    const last = status.last_synced_at ? new Date(status.last_synced_at).getTime() : 0;
    if (Date.now() - last > AUTO_SYNC_STALE_MS) {
      await sync(true);
    }
  }

  async function addTask(): Promise<void> {
    const title = quickAddTitle.trim();
    if (!title || !selectedDay) return;
    addingTask = true;
    try {
      const task = await api.calendarTasks.create({
        title,
        date: selectedDay,
        start_time: quickAddTime ? `${quickAddTime}:00` : null,
        priority: quickAddPriority,
        recurrence: quickAddRecurrence,
        reminder_minutes: quickAddReminder,
      });
      if (quickAddReminder !== null) void requestNotificationPermission();
      if (publishToGoogle && status?.connected) {
        try {
          const created = await api.google.calendarCreateEvent({
            summary: title,
            ...googleWindow(selectedDay, quickAddTime || null, null),
          });
          const mirrored = await api.calendarTasks.update(task.id, {
            google_event_id: created.google_id,
          });
          tasks = [...tasks, mirrored];
          await refresh();
        } catch (e) {
          logger.warn('Google publish failed', e);
          showNotification($t('calendar.googlePublishError'), 'error');
          tasks = [...tasks, task];
        }
      } else {
        tasks = [...tasks, task];
      }
      quickAddTitle = '';
      quickAddTime = '';
      quickAddPriority = 'MEDIUM';
      quickAddRecurrence = 'NONE';
      quickAddReminder = null;
    } catch (e) {
      logger.error(e);
      showNotification($t('calendar.taskAddError'), 'error');
    } finally {
      addingTask = false;
    }
  }

  async function addUnscheduledTask(): Promise<void> {
    const title = trayAddTitle.trim();
    if (!title) return;
    trayAdding = true;
    try {
      const task = await api.calendarTasks.create({ title, date: null });
      tasks = [...tasks, task];
      trayAddTitle = '';
    } catch (e) {
      logger.error(e);
      showNotification($t('calendar.taskAddError'), 'error');
    } finally {
      trayAdding = false;
    }
  }

  function addDays(dayKey: string, days: number): string {
    // Anchor at local noon so adding days across a DST transition stays
    // stable.
    const d = new Date(`${dayKey}T12:00:00`);
    d.setDate(d.getDate() + days);
    return localDayKey(d);
  }

  // `hhmm` on `day` plus one real hour, returned as `YYYY-MM-DDTHH:mm:ss`.
  // Date-based so 23:30 rolls into the next day — the old string math
  // wrapped to 00:30 on the same day, producing end < start which Google
  // rejects.
  function addHour(day: string, hhmm: string): string {
    const start = new Date(`${day}T${hhmm.slice(0, 5)}:00`);
    const end = new Date(start.getTime() + 3600e3);
    return `${localDayKey(end)}T${pad2(end.getHours())}:${pad2(end.getMinutes())}:00`;
  }

  // Build the Google EventDateTime pair for a task's window. All-day tasks
  // publish `{date}`; Google's end.date is EXCLUSIVE, so it must be the day
  // after — same-day start+end is a zero-length event Google rejects.
  // Timed tasks publish `dateTime` + `timeZone` so naive local times are
  // anchored to the browser zone.
  function googleWindow(
    day: string,
    startTime: string | null,
    endTime: string | null
  ): {
    start: { dateTime?: string; date?: string; timeZone?: string };
    end: { dateTime?: string; date?: string; timeZone?: string };
  } {
    if (!startTime) {
      return { start: { date: day }, end: { date: addDays(day, 1) } };
    }
    const hhmm = startTime.slice(0, 5);
    const end = endTime ? `${day}T${endTime.slice(0, 5)}:00` : addHour(day, hhmm);
    return {
      start: { dateTime: `${day}T${hhmm}:00`, timeZone: localTimeZone },
      end: { dateTime: end, timeZone: localTimeZone },
    };
  }

  function cyclePriority(task: CalendarTask): void {
    const idx = PRIORITIES.indexOf(task.priority);
    const next = PRIORITIES[(idx + 1) % PRIORITIES.length];
    updateTask(task, { priority: next });
  }

  async function updateTask(task: CalendarTask, patch: Partial<CalendarTask>): Promise<void> {
    try {
      const updated = await api.calendarTasks.update(task.id, patch);
      tasks = tasks.map((t) => (t.id === updated.id ? updated : t));
    } catch (e) {
      logger.error(e);
      showNotification($t('calendar.taskUpdateError'), 'error');
    }
  }

  async function toggleDone(task: CalendarTask): Promise<void> {
    try {
      const updated = await api.calendarTasks.toggleDone(task.id);
      tasks = tasks.map((t) => (t.id === updated.id ? updated : t));
    } catch (e) {
      logger.error(e);
      showNotification($t('calendar.taskUpdateError'), 'error');
    }
  }

  async function removeTask(task: CalendarTask): Promise<void> {
    try {
      if (task.google_event_id && status?.connected) {
        try {
          await api.google.calendarDeleteEvent(task.google_event_id);
        } catch (e) {
          logger.warn('Google delete failed', e);
          showNotification($t('calendar.googlePublishError'), 'error');
        }
      }
      await api.calendarTasks.remove(task.id);
      tasks = tasks.filter((t) => t.id !== task.id);
    } catch (e) {
      logger.error(e);
      showNotification($t('calendar.taskDeleteError'), 'error');
    }
  }

  function startEdit(task: CalendarTask): void {
    editingTaskId = task.id;
    editTitle = task.title;
    editTime = task.start_time ? task.start_time.slice(0, 5) : '';
    editEndTime = task.end_time ? task.end_time.slice(0, 5) : '';
    editRecurrence = task.recurrence;
    editReminder = task.reminder_minutes;
  }

  async function saveEdit(task: CalendarTask): Promise<void> {
    const title = editTitle.trim();
    if (!title) return;
    // Never persist an end ≤ start — Google rejects the inverted window
    // and a mirrored task would carry a broken dateTime pair (#1306).
    if (editTime && editEndTime && editEndTime <= editTime) {
      showNotification($t('calendar.endBeforeStart'), 'error');
      return;
    }
    if (editReminder !== null) void requestNotificationPermission();
    await updateTask(task, {
      title,
      start_time: editTime ? `${editTime}:00` : null,
      end_time: editEndTime ? `${editEndTime}:00` : null,
      recurrence: editRecurrence,
      reminder_minutes: editReminder,
    });
    if (task.google_event_id && status?.connected) {
      try {
        const day = task.date;
        // The edit form only lives in the day panel — unscheduled tasks
        // (date === null) never reach this path.
        if (!day) return;
        const { start, end } = googleWindow(day, editTime || null, editEndTime || null);
        await api.google.calendarUpdateEvent(task.google_event_id, {
          summary: title,
          start,
          end,
        });
        await refresh();
      } catch (e) {
        logger.warn('Google update failed', e);
        showNotification($t('calendar.googlePublishError'), 'error');
      }
    }
    editingTaskId = null;
  }

  // ── Drag & drop between days (#1236) ──────────────────────────────────────
  let draggedTask = $state<CalendarTask | null>(null);
  let dropTargetKey = $state<string | null>(null);

  function onChipDragStart(event: DragEvent, task: CalendarTask): void {
    draggedTask = task;
    event.dataTransfer?.setData('text/plain', String(task.id));
    if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
  }

  function onChipDragEnd(): void {
    draggedTask = null;
    dropTargetKey = null;
  }

  function onCellDragOver(event: DragEvent, cellKey: string): void {
    if (!draggedTask) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
    dropTargetKey = cellKey;
  }

  function onCellDragLeave(cellKey: string): void {
    if (dropTargetKey === cellKey) dropTargetKey = null;
  }

  function onCellDrop(event: DragEvent, cellKey: string): void {
    event.preventDefault();
    dropTargetKey = null;
    const task = draggedTask;
    draggedTask = null;
    if (!task || task.date === cellKey) return;
    rescheduleTask(task, cellKey);
  }

  async function rescheduleTask(task: CalendarTask, newDate: string): Promise<void> {
    const previousDate = task.date;
    // Optimistic update
    tasks = tasks.map((t) => (t.id === task.id ? { ...t, date: newDate } : t));
    try {
      const updated = await api.calendarTasks.update(task.id, { date: newDate });
      tasks = tasks.map((t) => (t.id === updated.id ? updated : t));
      showNotification($t('calendar.taskRescheduled'), 'success');
    } catch (e) {
      logger.error(e);
      // Rollback
      tasks = tasks.map((t) => (t.id === task.id ? { ...t, date: previousDate } : t));
      showNotification($t('calendar.taskUpdateError'), 'error');
      return;
    }
    // Write-back parity: drag&drop moves the mirrored Google event too.
    // A Google failure is non-blocking — the local reschedule stands.
    if (task.google_event_id && status?.connected) {
      try {
        const { start, end } = googleWindow(newDate, task.start_time, task.end_time);
        await api.google.calendarUpdateEvent(task.google_event_id, { start, end });
        await refresh();
      } catch (e) {
        logger.warn('Google reschedule failed', e);
        showNotification($t('calendar.googlePublishError'), 'error');
      }
    }
  }

  // ── Unscheduled tray drop target (#1234) ─────────────────────────────────
  let trayDropActive = $state(false);

  function onTrayDragOver(event: DragEvent): void {
    if (!draggedTask) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
    trayDropActive = true;
  }

  function onTrayDragLeave(): void {
    trayDropActive = false;
  }

  function onTrayDrop(event: DragEvent): void {
    event.preventDefault();
    trayDropActive = false;
    const task = draggedTask;
    draggedTask = null;
    dropTargetKey = null;
    if (!task || task.date === null) return;
    unscheduleTask(task);
  }

  async function unscheduleTask(task: CalendarTask): Promise<void> {
    const previousDate = task.date;
    // Optimistic update
    tasks = tasks.map((t) => (t.id === task.id ? { ...t, date: null } : t));
    try {
      const updated = await api.calendarTasks.update(task.id, { date: null });
      tasks = tasks.map((t) => (t.id === updated.id ? updated : t));
      showNotification($t('calendar.taskUnscheduled'), 'success');
    } catch (e) {
      logger.error(e);
      // Rollback
      tasks = tasks.map((t) => (t.id === task.id ? { ...t, date: previousDate } : t));
      showNotification($t('calendar.taskUpdateError'), 'error');
    }
  }

  function priorityClass(priority: CalendarTaskPriority): string {
    return `prio prio-${priority.toLowerCase()}`;
  }

  function openSettings(): void {
    window.dispatchEvent(new CustomEvent('joidy:open-settings'));
  }

  // Reminder polling (#1238): every 30s, surface today's tasks whose
  // reminder window opened. In-page MVP — the toast always fires, the
  // system Notification only when the user granted permission (requested
  // lazily on save, never on load).
  function checkTaskReminders(): void {
    for (const task of dueTaskReminders(tasks, new Date(), notifiedTaskIds)) {
      notifiedTaskIds.add(task.id);
      const when = task.start_time ? task.start_time.slice(0, 5) : '';
      const message = $t('calendar.taskReminder', { values: { title: task.title } });
      showNotification(message, 'info');
      fireTaskNotification(message, when);
    }
  }

  // ── AI plan suggestions (#1237) ─────────────────────────────────────────
  // Ghost slots proposed by the ai-service: rendered as dashed chips on the
  // affected day cells until the user accepts (PATCH task) or dismisses them.
  let planSuggestions = $state<PlanSuggestion[]>([]);
  let planLoading = $state(false);
  let planApplying = $state(false);

  let planByDay = $derived.by(() => {
    const map = new Map<string, PlanSuggestion[]>();
    for (const s of planSuggestions) {
      const list = map.get(s.date) ?? [];
      list.push(s);
      map.set(s.date, list);
    }
    return map;
  });

  function planTaskTitle(taskId: number): string {
    return tasks.find((t) => t.id === taskId)?.title ?? `#${taskId}`;
  }

  async function suggestPlan(): Promise<void> {
    if (planLoading) return;
    planLoading = true;
    planSuggestions = [];
    try {
      // The api rebuilds tasks + busy blocks from the DB for the range, so
      // only the window and zone are sent.
      const res = await api.ai.planSuggest({
        week_start: fetchRange.start,
        week_end: fetchRange.end,
        timezone: localTimeZone,
      });
      if (!res.available) {
        showNotification($t('calendar.planUnavailable'), 'info');
        return;
      }
      if (res.suggestions.length === 0) {
        showNotification($t('calendar.planEmpty'), 'info');
        return;
      }
      planSuggestions = res.suggestions;
    } catch (e) {
      logger.error(e);
      showNotification($t('calendar.planError'), 'error');
    } finally {
      planLoading = false;
    }
  }

  async function acceptSuggestion(sugg: PlanSuggestion): Promise<void> {
    try {
      const updated = await api.calendarTasks.update(sugg.task_id, {
        date: sugg.date,
        start_time: `${sugg.start_time.slice(0, 5)}:00`,
        end_time: sugg.end_time ? `${sugg.end_time.slice(0, 5)}:00` : null,
      });
      tasks = tasks.map((t) => (t.id === updated.id ? updated : t));
      planSuggestions = planSuggestions.filter((s) => s !== sugg);
    } catch (e) {
      logger.error(e);
      showNotification($t('calendar.taskUpdateError'), 'error');
    }
  }

  async function acceptAllSuggestions(): Promise<void> {
    if (planApplying) return;
    planApplying = true;
    try {
      for (const sugg of [...planSuggestions]) {
        await acceptSuggestion(sugg);
      }
      if (planSuggestions.length === 0) {
        showNotification($t('calendar.planApplied'), 'success');
      }
    } finally {
      planApplying = false;
    }
  }

  onMount(() => {
    void (async () => {
      await refresh();
      await maybeAutoSync();
    })();
    // The 30s reminder poll doubles as the midnight-rollover check: when the
    // day changed, ranges shift so events/tasks must be refetched (#1306).
    const timer = setInterval(() => {
      if (syncToday()) void refresh();
      checkTaskReminders();
    }, 30_000);
    // Throttled tabs may skip the interval past midnight — resync on focus.
    const onVisible = () => {
      if (document.visibilityState === 'visible' && syncToday()) void refresh();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  });
</script>

<svelte:head>
  <title>{$t('calendar.pageTitle')}</title>
</svelte:head>

<div class="calendar-page">
  <div class="calendar-header">
    <div>
      <h3>{$t('calendar.title')}</h3>
      <span class="caption">
        {#if status?.last_synced_at}
          {$t('calendar.lastSync', {
            values: { when: new Date(status.last_synced_at).toLocaleString() },
          })}
        {:else if status?.connected}
          {$t('calendar.neverSynced')}
        {:else}
          {$t('calendar.subtitle')}
        {/if}
      </span>
    </div>
    <div class="calendar-actions">
      <button class="btn btn-ghost" onclick={() => sync()} disabled={syncing || !status?.connected}>
        <span class={syncing ? 'spin' : ''}><RefreshCw size={13} /></span>
        {syncing ? $t('calendar.syncing') : $t('calendar.sync')}
      </button>
    </div>
  </div>

  {#if loading}
    <div class="loading-state caption">{$t('calendar.loading')}</div>
  {:else if loadError}
    <div class="empty-wrap">
      <EmptyState
        title={$t('calendar.loadError')}
        message={$t('calendar.loadErrorHint')}
        actionLabel={$t('common.retry')}
        onAction={() => {
          loading = true;
          void refresh();
        }}
      >
        {#snippet icon()}<RefreshCw size={44} />{/snippet}
      </EmptyState>
    </div>
  {:else if status && !status.connected}
    <div class="empty-wrap">
      <EmptyState
        title={$t('calendar.notConnected')}
        message={$t('calendar.notConnectedHint')}
        actionLabel={$t('calendar.goToSettings')}
        onAction={openSettings}
      >
        {#snippet icon()}<Settings size={44} />{/snippet}
      </EmptyState>
    </div>
  {:else}
    <div class="calendar-body">
      <div class="calendar-card">
        <div class="calendar-toolbar">
          <div class="view-switcher">
            <button
              class="btn btn-ghost view-btn"
              class:active={currentView === 'month'}
              aria-pressed={currentView === 'month'}
              onclick={() => setView('month')}>{$t('calendar.views.month')}</button
            >
            <button
              class="btn btn-ghost view-btn"
              class:active={currentView === 'week'}
              aria-pressed={currentView === 'week'}
              onclick={() => setView('week')}>{$t('calendar.views.week')}</button
            >
            <button
              class="btn btn-ghost view-btn"
              class:active={currentView === 'agenda'}
              aria-pressed={currentView === 'agenda'}
              onclick={() => setView('agenda')}>{$t('calendar.views.agenda')}</button
            >
          </div>

          {#if currentView !== 'agenda'}
            <button
              class="btn btn-ghost nav-btn"
              onclick={prevRange}
              aria-label={currentView === 'week'
                ? $t('calendar.prevWeek')
                : $t('calendar.prevMonth')}
            >
              <ChevronLeft size={16} />
            </button>
          {/if}

          <span class="month-label">
            {#if currentView === 'month'}
              {$t(`calendar.months.${viewMonth}`)} {viewYear}
            {:else if currentView === 'week'}
              {weekLabel}
            {:else}
              {$t('calendar.views.agenda')} (14 {$t('calendar.agendaDays')})
            {/if}
          </span>

          <button class="btn btn-ghost nav-btn" onclick={goToday}>{$t('calendar.today')}</button>

          {#if currentView !== 'agenda'}
            <button
              class="btn btn-ghost nav-btn"
              onclick={nextRange}
              aria-label={currentView === 'week'
                ? $t('calendar.nextWeek')
                : $t('calendar.nextMonth')}
            >
              <ChevronRight size={16} />
            </button>
          {/if}

          <button
            class="btn btn-ghost nav-btn plan-btn"
            onclick={suggestPlan}
            disabled={planLoading}
            title={$t('calendar.planSuggestHint')}
            aria-label={$t('calendar.planSuggest')}
          >
            <Sparkles size={14} class={planLoading ? 'spin' : ''} />
            <span class="plan-btn-label"
              >{planLoading ? $t('calendar.planWorking') : $t('calendar.planSuggest')}</span
            >
          </button>
        </div>

        {#if currentView === 'month'}
          <div class="weekday-row">
            {#each Array(7) as _, i}
              <span class="weekday caption">{$t(`calendar.weekDays.${i}`)}</span>
            {/each}
          </div>

          <div class="day-grid">
            {#each gridCells as cell (cell.key)}
              {@const items = monthItems.get(cell.key) ?? []}
              <button
                class="day-cell"
                class:out={!cell.inMonth}
                class:today={cell.key === todayKey}
                class:selected={selectedDay === cell.key}
                class:drop-target={dropTargetKey === cell.key}
                draggable={items.some((i) => i.kind === 'task')}
                ondragover={(e) => onCellDragOver(e, cell.key)}
                ondragleave={() => onCellDragLeave(cell.key)}
                ondrop={(e) => onCellDrop(e, cell.key)}
                onclick={() => (selectedDay = selectedDay === cell.key ? null : cell.key)}
              >
                <span class="day-num">{cell.day}</span>
                <span class="cell-items">
                  {#each items.slice(0, 2) as item}
                    {#if item.kind === 'google'}
                      <span class="chip chip-google"><Lock size={8} />{item.label}</span>
                    {:else}
                      <span
                        class="chip {priorityClass(item.task.priority)}"
                        class:done={item.task.done}
                        class:dragging={draggedTask?.id === item.task.id}
                        role="button"
                        tabindex="-1"
                        draggable="true"
                        ondragstart={(e) => onChipDragStart(e, item.task)}
                        ondragend={onChipDragEnd}
                        >{#if item.task.recurrence !== 'NONE'}<Repeat
                            size={8}
                            class="recur-icon"
                          />{/if}{item.label}</span
                      >
                    {/if}
                  {/each}
                  {#if items.length > 2}
                    <span class="chip chip-more">+{items.length - 2}</span>
                  {/if}
                  {#each planByDay.get(cell.key) ?? [] as sugg (sugg.task_id)}
                    <span
                      class="chip chip-ghost"
                      role="button"
                      tabindex="-1"
                      title={sugg.rationale || $t('calendar.planAcceptHint')}
                      onclick={(e) => {
                        e.stopPropagation();
                        acceptSuggestion(sugg);
                      }}
                      onkeydown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.stopPropagation();
                          acceptSuggestion(sugg);
                        }
                      }}><Sparkles size={7} />{sugg.start_time} {planTaskTitle(sugg.task_id)}</span
                    >
                  {/each}
                </span>
              </button>
            {/each}
          </div>
        {:else if currentView === 'week'}
          <div class="weekday-row">
            {#each weekDays as day}
              <span class="weekday caption" class:bold={day.key === todayKey}>
                {$t(`calendar.weekDays.${day.weekdayIndex}`)}
                {day.day}
              </span>
            {/each}
          </div>

          <div class="week-grid">
            {#each weekDays as day (day.key)}
              {@const items = monthItems.get(day.key) ?? []}
              <div
                class="week-col"
                class:today={day.key === todayKey}
                class:selected={selectedDay === day.key}
                class:drop-target={dropTargetKey === day.key}
                role="region"
                aria-label={day.key}
                ondragover={(e) => onCellDragOver(e, day.key)}
                ondragleave={() => onCellDragLeave(day.key)}
                ondrop={(e) => onCellDrop(e, day.key)}
              >
                <button
                  class="week-col-header"
                  onclick={() => (selectedDay = selectedDay === day.key ? null : day.key)}
                >
                  <span class="day-num">{day.day}</span>
                  <span class="caption">{items.length}</span>
                </button>
                <div class="week-col-items">
                  {#each items as item}
                    {#if item.kind === 'google'}
                      <div class="chip chip-google">
                        <Lock size={8} />
                        <span class="chip-time">{item.time || ''}</span>
                        <span class="chip-label">{item.label}</span>
                      </div>
                    {:else}
                      <div
                        class="chip {priorityClass(item.task.priority)}"
                        class:done={item.task.done}
                        class:dragging={draggedTask?.id === item.task.id}
                        role="button"
                        tabindex="-1"
                        draggable="true"
                        ondragstart={(e) => onChipDragStart(e, item.task)}
                        ondragend={onChipDragEnd}
                      >
                        {#if item.time}<span class="chip-time">{item.time}</span>{/if}
                        {#if item.task.recurrence !== 'NONE'}<Repeat
                            size={8}
                            class="recur-icon"
                          />{/if}
                        <span class="chip-label">{item.label}</span>
                      </div>
                    {/if}
                  {/each}
                  {#each planByDay.get(day.key) ?? [] as sugg (sugg.task_id)}
                    <button
                      class="chip chip-ghost"
                      title={sugg.rationale || $t('calendar.planAcceptHint')}
                      onclick={() => acceptSuggestion(sugg)}
                    >
                      <Sparkles size={7} />
                      <span class="chip-time">{sugg.start_time}</span>
                      <span class="chip-label">{planTaskTitle(sugg.task_id)}</span>
                    </button>
                  {/each}
                </div>
              </div>
            {/each}
          </div>
        {:else if currentView === 'agenda'}
          <div class="agenda-view">
            {#each agendaDays as day (day.key)}
              <div
                class="agenda-day-row"
                class:today={day.key === todayKey}
                class:selected={selectedDay === day.key}
                role="button"
                tabindex="0"
                onclick={() => (selectedDay = selectedDay === day.key ? null : day.key)}
                onkeydown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    selectedDay = selectedDay === day.key ? null : day.key;
                  }
                }}
              >
                <div class="agenda-date-badge">
                  <span class="day-num">{day.date.getDate()}</span>
                  <span class="caption"
                    >{day.date.toLocaleDateString(undefined, {
                      weekday: 'short',
                      month: 'short',
                    })}</span
                  >
                </div>
                <div class="agenda-day-items">
                  {#if day.items.length === 0}
                    <span class="caption empty-agenda-day">{$t('calendar.noEventsDay')}</span>
                  {:else}
                    {#each day.items as item}
                      <div
                        class="agenda-item-pill"
                        class:done={item.kind === 'task' && item.task.done}
                      >
                        {#if item.kind === 'google'}
                          <Lock size={9} class="lock-icon" />
                          <span class="chip-time caption"
                            >{item.allDay ? $t('calendar.allDay') : item.time}</span
                          >
                          <span class="pill-title">{item.label}</span>
                        {:else}
                          <span class="priority-dot {priorityClass(item.task.priority)}"></span>
                          {#if item.time}<span class="chip-time caption">{item.time}</span>{/if}
                          {#if item.task.recurrence !== 'NONE'}<Repeat
                              size={9}
                              class="recur-icon"
                            />{/if}
                          <span class="pill-title">{item.label}</span>
                        {/if}
                      </div>
                    {/each}
                  {/if}
                  {#each planByDay.get(day.key) ?? [] as sugg (sugg.task_id)}
                    <button
                      class="agenda-item-pill chip-ghost"
                      title={sugg.rationale || $t('calendar.planAcceptHint')}
                      onclick={(e) => {
                        e.stopPropagation();
                        acceptSuggestion(sugg);
                      }}
                    >
                      <Sparkles size={9} class="lock-icon" />
                      <span class="chip-time caption">{sugg.start_time}</span>
                      <span class="pill-title">{planTaskTitle(sugg.task_id)}</span>
                    </button>
                  {/each}
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <div class="day-detail">
        {#if planSuggestions.length > 0}
          <div class="plan-bar">
            <span class="plan-bar-title caption">
              <Sparkles size={11} />{$t('calendar.planPending', {
                values: { count: planSuggestions.length },
              })}
            </span>
            <div class="plan-bar-actions">
              <button
                class="btn btn-ghost plan-bar-btn"
                onclick={acceptAllSuggestions}
                disabled={planApplying}>{$t('calendar.planAcceptAll')}</button
              >
              <button
                class="btn btn-ghost plan-bar-btn"
                onclick={() => (planSuggestions = [])}
                disabled={planApplying}>{$t('calendar.planDismiss')}</button
              >
            </div>
          </div>
        {/if}
        {#if selectedDay}
          <h4>
            {new Date(`${selectedDay}T12:00:00`).toLocaleDateString(undefined, {
              weekday: 'long',
              day: 'numeric',
              month: 'long',
            })}
          </h4>
          {#if selectedDayItems.length === 0}
            <span class="caption">{$t('calendar.noEventsDay')}</span>
          {:else}
            <div class="event-list">
              {#each selectedDayItems as item (item.kind === 'google' ? `g-${item.id}` : `t-${item.task.id}`)}
                {#if item.kind === 'google'}
                  <div class="event-item">
                    <span class="event-time caption"
                      >{item.allDay ? $t('calendar.allDay') : item.time}</span
                    >
                    <span class="event-summary"
                      ><Lock size={10} class="lock-icon" /> {item.label}</span
                    >
                    {#if item.location}
                      <span class="event-location caption">{item.location}</span>
                    {/if}
                  </div>
                {:else}
                  <div class="event-item task-item" class:done={item.task.done}>
                    {#if editingTaskId === item.task.id}
                      <div class="edit-form">
                        <input
                          class="input edit-input"
                          type="text"
                          bind:value={editTitle}
                          maxlength="500"
                          aria-label={$t('calendar.editTitle')}
                        />
                        <div class="edit-times">
                          <input class="input edit-input" type="time" bind:value={editTime} aria-label={$t('calendar.startTime')} />
                          <input class="input edit-input" type="time" bind:value={editEndTime} aria-label={$t('calendar.endTime')} />
                        </div>
                        <div class="edit-times">
                          <select
                            class="input edit-input"
                            bind:value={editRecurrence}
                            aria-label={$t('calendar.recurrence')}
                          >
                            {#each RECURRENCE_OPTIONS as opt (opt.labelKey)}
                              <option value={opt.value}>{$t(`calendar.${opt.labelKey}`)}</option>
                            {/each}
                          </select>
                          <select
                            class="input edit-input"
                            bind:value={editReminder}
                            aria-label={$t('calendar.reminder')}
                          >
                            {#each REMINDER_OPTIONS as opt (opt.labelKey)}
                              <option value={opt.minutes}>{$t(`calendar.${opt.labelKey}`)}</option>
                            {/each}
                          </select>
                        </div>
                        <div class="edit-actions">
                          <button
                            class="btn btn-ghost icon-btn"
                            onclick={() => saveEdit(item.task)}
                            aria-label={$t('calendar.save')}
                          >
                            <Check size={13} />
                          </button>
                          <button
                            class="btn btn-ghost icon-btn"
                            onclick={() => (editingTaskId = null)}
                            aria-label={$t('calendar.cancel')}
                          >
                            <X size={13} />
                          </button>
                        </div>
                      </div>
                    {:else}
                      <button
                        class="done-btn"
                        class:checked={item.task.done}
                        onclick={() => toggleDone(item.task)}
                        aria-label={$t('calendar.toggleDone')}
                      >
                        <Check size={12} />
                      </button>
                      <span class="event-time caption">{item.time ?? '·'}</span>
                      <button
                        class="prio-btn {priorityClass(item.task.priority)}"
                        onclick={() => cyclePriority(item.task)}
                        title={$t('calendar.priority')}
                        aria-label={$t('calendar.priority')}
                      >
                        {item.task.priority.slice(0, 1)}
                      </button>
                      <span class="event-summary"
                        >{#if item.task.recurrence !== 'NONE'}<Repeat
                            size={10}
                            class="recur-icon"
                          />{/if}{item.task.title}</span
                      >
                      <span class="task-actions">
                        <button
                          class="btn btn-ghost icon-btn"
                          onclick={() => startEdit(item.task)}
                          aria-label={$t('calendar.edit')}
                        >
                          <Pencil size={12} />
                        </button>
                        <button
                          class="btn btn-ghost icon-btn"
                          onclick={() => removeTask(item.task)}
                          aria-label={$t('calendar.delete')}
                        >
                          <Trash2 size={12} />
                        </button>
                      </span>
                    {/if}
                  </div>
                {/if}
              {/each}
            </div>
          {/if}

          <form
            class="quick-add"
            onsubmit={(e) => {
              e.preventDefault();
              addTask();
            }}
          >
            <input
              class="input quick-input"
              type="text"
              bind:value={quickAddTitle}
              placeholder={$t('calendar.quickAddPlaceholder')}
              aria-label={$t('calendar.quickAddPlaceholder')}
              maxlength="500"
              disabled={addingTask}
            />
            <input
              class="input quick-time"
              type="time"
              bind:value={quickAddTime}
              aria-label={$t('calendar.startTime')}
              disabled={addingTask}
            />
            <select
              class="input quick-prio"
              bind:value={quickAddPriority}
              disabled={addingTask}
              aria-label={$t('calendar.priority')}
            >
              {#each PRIORITIES as p}
                <option value={p}>{p}</option>
              {/each}
            </select>
            <select
              class="input quick-prio"
              bind:value={quickAddRecurrence}
              disabled={addingTask}
              aria-label={$t('calendar.recurrence')}
              title={$t('calendar.recurrence')}
            >
              {#each RECURRENCE_OPTIONS as opt (opt.labelKey)}
                <option value={opt.value}>{$t(`calendar.${opt.labelKey}`)}</option>
              {/each}
            </select>
            <select
              class="input quick-prio"
              bind:value={quickAddReminder}
              disabled={addingTask}
              aria-label={$t('calendar.reminder')}
              title={$t('calendar.reminder')}
            >
              {#each REMINDER_OPTIONS as opt (opt.labelKey)}
                <option value={opt.minutes}>{$t(`calendar.${opt.labelKey}`)}</option>
              {/each}
            </select>
            {#if status?.connected}
              <label class="publish-toggle" title={$t('calendar.publishToGoogleHint')}>
                <input type="checkbox" bind:checked={publishToGoogle} disabled={addingTask} />
                <span class="publish-label"><Lock size={10} />{$t('calendar.publishToGoogle')}</span
                >
              </label>
            {/if}
            <button
              type="submit"
              class="btn btn-icon quick-submit"
              disabled={addingTask || !quickAddTitle.trim()}
              aria-label={$t('calendar.addTask')}
            >
              <Plus size={14} />
            </button>
          </form>
        {:else}
          <h4>{$t('calendar.pickDay')}</h4>
          <span class="caption">{$t('calendar.pickDayHint')}</span>
        {/if}
      </div>
    </div>

    <div
      class="unscheduled-tray"
      class:collapsed={trayCollapsed}
      class:drop-target={trayDropActive}
      role="region"
      aria-label={$t('calendar.unscheduled')}
      ondragover={onTrayDragOver}
      ondragleave={onTrayDragLeave}
      ondrop={onTrayDrop}
    >
      <div class="tray-header">
        <button
          class="btn btn-ghost tray-toggle"
          onclick={toggleTray}
          aria-expanded={!trayCollapsed}
          aria-label={$t('calendar.unscheduled')}
        >
          <ChevronDown size={14} class={trayCollapsed ? 'tray-chevron' : 'tray-chevron open'} />
          <Inbox size={13} />
          <span>{$t('calendar.unscheduled')}</span>
          <span class="tray-count caption">{unscheduledTasks.length}</span>
        </button>
        {#if !trayCollapsed}
          <form
            class="tray-add"
            onsubmit={(e) => {
              e.preventDefault();
              addUnscheduledTask();
            }}
          >
            <input
              class="input tray-add-input"
              type="text"
              bind:value={trayAddTitle}
              placeholder={$t('calendar.unscheduledAddPlaceholder')}
              aria-label={$t('calendar.unscheduledAddPlaceholder')}
              maxlength="500"
              disabled={trayAdding}
            />
            <button
              type="submit"
              class="btn btn-icon quick-submit"
              disabled={trayAdding || !trayAddTitle.trim()}
              aria-label={$t('calendar.addTask')}
            >
              <Plus size={14} />
            </button>
          </form>
        {/if}
      </div>
      {#if !trayCollapsed}
        {#if unscheduledTasks.length === 0}
          <span class="caption tray-empty">{$t('calendar.unscheduledEmpty')}</span>
        {:else}
          <div class="tray-items">
            {#each unscheduledTasks as task (task.id)}
              <div
                class="tray-task"
                class:done={task.done}
                class:dragging={draggedTask?.id === task.id}
                role="button"
                tabindex="-1"
                draggable="true"
                ondragstart={(e) => onChipDragStart(e, task)}
                ondragend={onChipDragEnd}
              >
                <button
                  class="done-btn"
                  class:checked={task.done}
                  onclick={() => toggleDone(task)}
                  aria-label={$t('calendar.toggleDone')}
                >
                  <Check size={12} />
                </button>
                <span class="priority-dot {priorityClass(task.priority)}"></span>
                {#if task.recurrence !== 'NONE'}<Repeat size={10} class="recur-icon" />{/if}
                <span class="tray-task-title">{task.title}</span>
                <button
                  class="btn btn-ghost icon-btn"
                  onclick={() => removeTask(task)}
                  aria-label={$t('calendar.delete')}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            {/each}
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  .calendar-page {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--s4) var(--s3);
    width: 100%;
    flex: 1;
    min-height: 0;
    box-sizing: border-box;
    overflow: hidden;
  }

  .calendar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-shrink: 0;
  }

  .calendar-header h3 {
    margin: 0;
  }

  .calendar-actions {
    display: flex;
    gap: 8px;
  }

  .calendar-body {
    display: grid;
    grid-template-columns: 1fr minmax(280px, 340px);
    grid-template-rows: 1fr;
    gap: 12px;
    flex: 1;
    min-height: 0;
  }

  .calendar-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3);
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .view-switcher {
    display: inline-flex;
    align-items: center;
    background: var(--surface-2, rgba(255, 255, 255, 0.04));
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 2px;
    gap: 2px;
  }

  .view-btn {
    font-size: 11px;
    padding: 3px 8px;
    border-radius: calc(var(--r) * 0.7);
    color: var(--text-muted);
    border: none;
    transition: all 0.15s ease;
  }

  .view-btn:hover {
    color: var(--text-primary);
  }

  .view-btn.active {
    background: var(--surface);
    color: var(--xp);
    font-weight: 600;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
  }

  .weekday.bold {
    font-weight: 700;
    color: var(--xp);
  }

  /* Week Grid */
  .week-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    grid-template-rows: 1fr;
    gap: 6px;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .week-col {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border);
    border-radius: calc(var(--r) * 0.7);
    background: var(--surface-2, rgba(255, 255, 255, 0.02));
    min-height: 0;
    overflow: hidden;
    transition: border-color 0.15s ease;
  }

  .week-col.today {
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 8%, transparent);
  }

  .week-col.selected {
    border-color: var(--xp);
    box-shadow: 0 0 0 1px var(--xp);
  }

  .week-col.drop-target {
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 18%, transparent);
  }

  .week-col-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 6px;
    border: none;
    border-bottom: 1px solid var(--border);
    background: transparent;
    cursor: pointer;
    color: inherit;
    width: 100%;
  }

  .week-col-header:hover {
    background: var(--hover);
  }

  .week-col-items {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 6px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }

  .week-col-items .chip {
    display: flex;
    align-items: center;
    gap: 4px;
    width: 100%;
    box-sizing: border-box;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .chip-time {
    font-size: 9px;
    opacity: 0.75;
    flex-shrink: 0;
  }

  .chip-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }

  /* Agenda View */
  .agenda-view {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding-right: 4px;
  }

  .agenda-day-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface-2, rgba(255, 255, 255, 0.02));
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .agenda-day-row:hover {
    background: var(--hover);
  }

  .agenda-day-row.today {
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 10%, transparent);
  }

  .agenda-day-row.selected {
    border-color: var(--xp);
    box-shadow: 0 0 0 1px var(--xp);
  }

  .agenda-date-badge {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-width: 48px;
    padding: 4px;
    border-radius: calc(var(--r) * 0.6);
    background: var(--surface);
    border: 1px solid var(--border);
    flex-shrink: 0;
  }

  .agenda-date-badge .day-num {
    font-size: 15px;
    font-weight: 700;
    line-height: 1;
  }

  .agenda-date-badge .caption {
    font-size: 10px;
    text-transform: capitalize;
  }

  .agenda-day-items {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    flex: 1;
    min-height: 28px;
  }

  .empty-agenda-day {
    font-style: italic;
    opacity: 0.5;
  }

  .agenda-item-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 8px;
    border-radius: 999px;
    background: var(--surface);
    border: 1px solid var(--border);
    font-size: 11px;
    max-width: 260px;
  }

  .agenda-item-pill.done {
    opacity: 0.55;
    text-decoration: line-through;
  }

  .pill-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .priority-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .priority-dot.prio-high {
    background: var(--danger, #ef4444);
  }

  .priority-dot.prio-medium {
    background: var(--xp, #c8a96e);
  }

  .priority-dot.prio-low {
    background: var(--text-muted);
  }

  .calendar-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: var(--s2);
    flex-shrink: 0;
  }

  .month-label {
    flex: 1;
    text-align: center;
    font-weight: 600;
  }

  .nav-btn {
    padding: 4px 8px;
  }

  .weekday-row {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 4px;
    margin-bottom: 4px;
    flex-shrink: 0;
  }

  .weekday {
    text-align: center;
    font-size: 11px;
  }

  .day-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    grid-template-rows: repeat(6, 1fr);
    gap: 4px;
    flex: 1;
    min-height: 0;
  }

  .day-cell {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    justify-content: flex-start;
    gap: 2px;
    padding: 3px 4px;
    border: 1px solid transparent;
    border-radius: calc(var(--r) * 0.6);
    background: transparent;
    cursor: pointer;
    color: var(--text-primary);
    font-size: 11px;
    min-height: 0;
    overflow: hidden;
    text-align: left;
  }

  .day-cell:hover {
    background: var(--hover);
  }

  .day-cell.out {
    color: var(--text-muted);
    opacity: 0.5;
  }

  .day-cell.today {
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 12%, transparent);
  }

  .day-cell.today .day-num {
    color: var(--xp);
    font-weight: 700;
  }

  .day-cell.selected {
    background: var(--xp);
    color: var(--bg);
  }

  .day-cell.selected .day-num {
    color: var(--bg);
    font-weight: 700;
  }

  .day-cell.selected .chip {
    background: rgba(0, 0, 0, 0.15);
    color: var(--bg);
  }

  .day-cell.selected:hover {
    background: var(--xp-2);
  }

  .day-num {
    font-size: 12px;
    width: 100%;
    text-align: left;
  }

  .cell-items {
    display: flex;
    flex-direction: column;
    gap: 1px;
    width: 100%;
    min-width: 0;
  }

  .chip {
    display: flex;
    align-items: center;
    gap: 3px;
    font-size: 9px;
    line-height: 1.2;
    padding: 0 3px;
    border-radius: 3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
    background: color-mix(in srgb, var(--text-muted) 15%, transparent);
  }

  .chip-google {
    color: var(--text-muted);
  }

  .chip.done {
    text-decoration: line-through;
    opacity: 0.55;
  }

  .chip.dragging {
    opacity: 0.35;
  }

  .day-cell.drop-target {
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 18%, transparent);
  }

  .chip-more {
    color: var(--text-muted);
    background: transparent;
  }

  .prio-low {
    color: var(--text-muted);
  }
  .prio-medium {
    color: var(--accent);
  }
  .prio-high {
    color: #e08c3a;
  }
  .prio-urgent {
    color: #d9534f;
  }

  /* Non-color priority cues (#1309, WCAG 1.4.1): level stays perceivable
     through font style/weight even without color. */
  .prio-medium {
    font-style: italic;
  }
  .prio-high {
    font-weight: 600;
  }
  .prio-urgent {
    font-weight: 700;
    text-decoration: underline;
  }

  .day-detail {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3);
    overflow-y: auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s2);
  }

  .day-detail h4 {
    margin: 0;
    text-transform: capitalize;
  }

  .event-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .event-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border: 1px solid var(--border);
    border-radius: calc(var(--r) * 0.6);
  }

  .event-item.done {
    opacity: 0.55;
  }

  .event-item.done .event-summary {
    text-decoration: line-through;
  }

  .event-time {
    min-width: 44px;
    font-variant-numeric: tabular-nums;
  }

  .event-summary {
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .lock-icon {
    flex-shrink: 0;
    opacity: 0.6;
  }

  .recur-icon {
    flex-shrink: 0;
    opacity: 0.6;
  }

  .event-location {
    margin-left: auto;
    text-align: right;
  }

  .task-actions {
    margin-left: auto;
    display: flex;
    gap: 2px;
  }

  .icon-btn {
    padding: 3px;
  }

  .done-btn {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 4px;
    width: 18px;
    height: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: transparent;
    flex-shrink: 0;
  }

  .done-btn:hover {
    border-color: var(--accent);
  }

  .done-btn.checked {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
  }

  .prio-btn {
    border: none;
    border-radius: 4px;
    width: 20px;
    height: 18px;
    font-size: 10px;
    font-weight: 700;
    cursor: pointer;
    background: color-mix(in srgb, var(--text-muted) 15%, transparent);
    flex-shrink: 0;
  }

  .quick-add {
    display: flex;
    gap: 6px;
    margin-top: auto;
    padding-top: var(--s2);
    border-top: 1px solid var(--border);
    flex-shrink: 0;
  }

  .quick-input {
    flex: 1;
    min-width: 0;
    padding: var(--s2) var(--s3);
    font-size: 12px;
  }

  .quick-time,
  .quick-prio {
    width: auto;
    flex-shrink: 0;
    padding: var(--s2) var(--s2);
    font-size: 12px;
  }

  .quick-prio {
    max-width: 90px;
  }

  .quick-submit {
    flex-shrink: 0;
    width: 30px;
    height: 30px;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
  }

  .quick-submit:not(:disabled):hover {
    color: var(--text-primary);
    border-color: var(--border);
    background: var(--elevated);
  }

  .quick-submit:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .publish-toggle {
    display: flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
    flex-shrink: 0;
    font-size: 10px;
    color: var(--text-muted);
    user-select: none;
    position: relative;
  }

  /* Visually hidden but focusable: display:none would remove the checkbox
     from the tab order entirely (#1268). */
  .publish-toggle input {
    position: absolute;
    opacity: 0;
    width: 1px;
    height: 1px;
    margin: 0;
    pointer-events: none;
  }

  .publish-toggle input:focus-visible + .publish-label {
    outline: 2px solid var(--xp);
    outline-offset: 2px;
  }

  .publish-label {
    display: flex;
    align-items: center;
    gap: 3px;
    padding: 2px 6px;
    border: 1px solid var(--border);
    border-radius: 99px;
    transition: all 0.15s;
  }

  .publish-toggle input:checked + .publish-label {
    border-color: var(--accent);
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 10%, transparent);
  }

  .edit-form {
    display: flex;
    flex-direction: column;
    gap: 6px;
    width: 100%;
  }

  .edit-times {
    display: flex;
    gap: 6px;
  }

  .edit-input {
    width: 100%;
  }

  .edit-actions {
    display: flex;
    gap: 4px;
  }

  /* Unscheduled tray ("sin planificar", #1234) */
  .unscheduled-tray {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s2) var(--s3);
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 30%;
    min-height: 0;
    transition: border-color 0.15s ease;
  }

  .unscheduled-tray.drop-target {
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 12%, transparent);
  }

  .tray-header {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .tray-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 2px 6px;
    font-size: 12px;
    font-weight: 600;
  }

  .tray-chevron {
    transition: transform 0.15s ease;
  }

  .tray-chevron.open {
    transform: rotate(180deg);
  }

  .tray-count {
    background: var(--surface-2, rgba(255, 255, 255, 0.06));
    border: 1px solid var(--border);
    border-radius: 99px;
    padding: 0 6px;
    font-size: 10px;
  }

  .tray-add {
    display: flex;
    gap: 6px;
    flex: 1;
    min-width: 0;
    justify-content: flex-end;
  }

  .tray-add-input {
    max-width: 280px;
    flex: 1;
    min-width: 0;
    padding: var(--s1) var(--s2);
    font-size: 12px;
  }

  .tray-empty {
    font-style: italic;
    opacity: 0.6;
  }

  .tray-items {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    overflow-y: auto;
    min-height: 0;
  }

  .tray-task {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    border: 1px solid var(--border);
    border-radius: calc(var(--r) * 0.6);
    background: var(--surface-2, rgba(255, 255, 255, 0.02));
    font-size: 11px;
    max-width: 320px;
    cursor: grab;
  }

  .tray-task.done {
    opacity: 0.55;
  }

  .tray-task.done .tray-task-title {
    text-decoration: line-through;
  }

  .tray-task.dragging {
    opacity: 0.35;
  }

  .tray-task-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tray-task .icon-btn {
    margin-left: auto;
  }

  .empty-wrap {
    padding: var(--s4) 0;
  }

  .spin {
    animation: spin 1s linear infinite;
  }

  /* AI plan suggestions (#1237) — ghost preview chips + action bar */
  .plan-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-left: auto;
  }

  .plan-btn-label {
    font-size: 11px;
  }

  .chip-ghost {
    border: 1px dashed var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    color: var(--accent);
    opacity: 0.8;
    cursor: pointer;
  }

  .chip-ghost:hover {
    opacity: 1;
    background: color-mix(in srgb, var(--accent) 22%, transparent);
  }

  .plan-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 6px 8px;
    border: 1px dashed var(--accent);
    border-radius: calc(var(--r) * 0.6);
    background: color-mix(in srgb, var(--accent) 8%, transparent);
    flex-shrink: 0;
  }

  .plan-bar-title {
    display: flex;
    align-items: center;
    gap: 5px;
    font-weight: 600;
    color: var(--accent);
  }

  .plan-bar-actions {
    display: flex;
    gap: 4px;
  }

  .plan-bar-btn {
    font-size: 11px;
    padding: 3px 8px;
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  @media (max-width: 640px) {
    .calendar-body {
      grid-template-columns: 1fr;
      grid-template-rows: minmax(0, 3fr) minmax(0, 2fr);
    }

    .event-location {
      display: none;
    }
  }
</style>
