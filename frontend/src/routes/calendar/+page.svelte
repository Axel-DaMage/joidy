<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    api,
    type CalendarDayMetrics,
    type CalendarEvent,
    type CalendarTask,
    type CalendarTaskPriority,
    type CalendarTaskRecurrence,
    type Goal,
    type GoogleCalendarListItem,
    type PlanSuggestion,
  } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import { locale } from '$lib/stores/locale';
  import { parseLocalDate } from '$lib/utils/date';
  import { showNotification } from '$lib/stores/notifications';
  import { appHeaderTabs } from '$lib/stores/appHeader';
  import {
    dueTaskReminders,
    fireTaskNotification,
    requestNotificationPermission,
  } from '$lib/utils/taskReminders';
  import {
    addDays,
    buildItemsByDay,
    loadCalendarPrefs,
    metricsByDay as indexMetrics,
    monthCells,
    planSuggestionsByDay,
    saveCalendarPrefs,
    weekDayKeys,
    type CalendarView,
    type DayItem,
  } from '$lib/components/calendar/types';
  import MiniMonth from '$lib/components/calendar/MiniMonth.svelte';
  import MonthGrid from '$lib/components/calendar/MonthGrid.svelte';
  import TimeGrid from '$lib/components/calendar/TimeGrid.svelte';
  import AgendaList from '$lib/components/calendar/AgendaList.svelte';
  import YearGrid from '$lib/components/calendar/YearGrid.svelte';
  import EventEditor, {
    type EventEditorSave,
    type GoogleEventSave,
  } from '$lib/components/calendar/EventEditor.svelte';
  import DayBadges from '$lib/components/calendar/DayBadges.svelte';
  import ChevronLeft from 'lucide-svelte/icons/chevron-left';
  import ChevronRight from 'lucide-svelte/icons/chevron-right';
  import ChevronDown from 'lucide-svelte/icons/chevron-down';
  import CalendarDays from 'lucide-svelte/icons/calendar-days';
  import CalendarRange from 'lucide-svelte/icons/calendar-range';
  import CalendarClock from 'lucide-svelte/icons/calendar-clock';
  import ListTodo from 'lucide-svelte/icons/list-todo';
  import Calendar from 'lucide-svelte/icons/calendar';
  import Inbox from 'lucide-svelte/icons/inbox';
  import RefreshCw from 'lucide-svelte/icons/refresh-cw';
  import Settings from 'lucide-svelte/icons/settings';
  import Lock from 'lucide-svelte/icons/lock';
  import Plus from 'lucide-svelte/icons/plus';
  import Trash2 from 'lucide-svelte/icons/trash-2';
  import Check from 'lucide-svelte/icons/check';
  import Repeat from 'lucide-svelte/icons/repeat';
  import Sparkles from 'lucide-svelte/icons/sparkles';
  import Search from 'lucide-svelte/icons/search';
  import Flame from 'lucide-svelte/icons/flame';
  import EyeOff from 'lucide-svelte/icons/eye-off';
  import NotebookPen from 'lucide-svelte/icons/notebook-pen';
  import MapPin from 'lucide-svelte/icons/map-pin';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { t } from 'svelte-i18n';

  interface CalendarStatus {
    connected: boolean;
    calendars: number;
    cached_events: number;
    last_synced_at: string | null;
  }

  const PRIORITIES: CalendarTaskPriority[] = ['LOW', 'MEDIUM', 'HIGH', 'URGENT'];
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

  const AGENDA_DAYS = 14;

  // ── Persisted view preferences (#1658) ─────────────────────────────────────
  const prefs = loadCalendarPrefs();

  let events: CalendarEvent[] = $state([]);
  let tasks: CalendarTask[] = $state([]);
  let status: CalendarStatus | null = $state(null);
  let dayMetrics: CalendarDayMetrics[] = $state([]);
  let googleCalendars: GoogleCalendarListItem[] = $state([]);
  let goals: Goal[] = $state([]);
  let loading = $state(true);
  let loadError = $state(false);
  let syncing = $state(false);

  let currentView = $state<CalendarView>(prefs.view);
  let heatmap = $state(prefs.heatmap);
  let showMetrics = $state(prefs.showMetrics);
  let trayCollapsed = $state(prefs.trayCollapsed);
  let hiddenCalendarIds = $state<Set<string>>(new Set(prefs.hiddenCalendarIds));
  let showJoidyTasks = $state(true);
  let searchQuery = $state('');

  // Single navigation anchor: every view derives its range from this day.
  let anchorKey = $state(
    (() => {
      const d = new Date();
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    })()
  );
  let selectedDay = $state<string | null>(null);

  // Quick-add state (day panel)
  let quickAddTitle = $state('');
  let quickAddTime = $state('');
  let quickAddPriority = $state<CalendarTaskPriority>('MEDIUM');
  let quickAddRecurrence = $state<CalendarTaskRecurrence>('NONE');
  let quickAddReminder = $state<number | null>(null);
  let addingTask = $state(false);
  let trayAddTitle = $state('');
  let trayAdding = $state(false);

  // Event editor modal
  let editorOpen = $state(false);
  let editorMode = $state<'create' | 'edit-task' | 'edit-google'>('create');
  let editorTask = $state<CalendarTask | null>(null);
  let editorGoogleEvent = $state<CalendarEvent | null>(null);
  let editorInitialDate = $state<string | null>(null);
  let editorInitialTime = $state<string | null>(null);
  let editorSaving = $state(false);

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

  let todayKey = $state(currentDayKey());

  // Re-derive "today" after a midnight rollover (#1306). A selection pinned
  // to the old "today" follows the new day; explicit picks are left alone.
  function syncToday(): boolean {
    const next = currentDayKey();
    if (next === todayKey) return false;
    const prev = todayKey;
    todayKey = next;
    if (selectedDay === prev) selectedDay = next;
    return true;
  }

  function persistPrefs(): void {
    saveCalendarPrefs({
      view: currentView,
      heatmap,
      showMetrics,
      hiddenCalendarIds: [...hiddenCalendarIds],
      trayCollapsed,
    });
  }

  function setView(view: CalendarView): void {
    currentView = view;
    persistPrefs();
  }

  // Page tabs live in the global app header (cleared on unmount).
  $effect(() => {
    appHeaderTabs.set({
      label: $t('calendar.viewsLabel'),
      activeId: currentView,
      onselect: (id) => {
        if (id === 'month' || id === 'week' || id === 'day' || id === 'agenda' || id === 'year') {
          setView(id);
        }
      },
      tabs: [
        { id: 'month', label: $t('calendar.views.month'), icon: CalendarDays },
        { id: 'week', label: $t('calendar.views.week'), icon: CalendarRange },
        { id: 'day', label: $t('calendar.views.day'), icon: CalendarClock },
        { id: 'agenda', label: $t('calendar.views.agenda'), icon: ListTodo },
        { id: 'year', label: $t('calendar.views.year'), icon: Calendar },
      ],
    });
  });
  onDestroy(() => appHeaderTabs.set(null));

  // ── Derived ranges ─────────────────────────────────────────────────────────
  let anchorDate = $derived(parseLocalDate(anchorKey));
  let viewYear = $derived(anchorDate.getFullYear());
  let viewMonth = $derived(anchorDate.getMonth());
  let gridCells = $derived(monthCells(viewYear, viewMonth));
  let weekKeys = $derived(weekDayKeys(anchorKey));
  let agendaDays = $derived(
    Array.from({ length: AGENDA_DAYS }, (_, i) => {
      const key = addDays(anchorKey, i);
      return { date: parseLocalDate(key), key, items: itemsByDay.get(key) ?? [] };
    })
  );

  // Per-calendar colors for Google chips (GoogleCalendarListItem.backgroundColor).
  let calendarColors = $derived(
    new Map(
      googleCalendars
        .filter((c) => c.backgroundColor)
        .map((c) => [c.id, c.backgroundColor as string])
    )
  );

  let itemsByDay = $derived(
    buildItemsByDay(events, showJoidyTasks ? tasks : [], {
      hiddenCalendarIds,
      calendarColors,
      dtFormatter,
      query: searchQuery,
    })
  );

  let metricsMap = $derived(indexMetrics(dayMetrics));
  let selectedDayItems = $derived(
    selectedDay ? (itemsByDay.get(selectedDay) ?? []) : []
  );
  let selectedDayMetrics = $derived(selectedDay ? metricsMap.get(selectedDay) : undefined);

  let unscheduledTasks = $derived(
    tasks.filter((t) => t.date === null).sort((a, b) => a.created_at.localeCompare(b.created_at))
  );

  // Union of every view's visible day range — bounds the cached-events and
  // task fetches so we never pull the whole table. The year bounds only join
  // in year view: elsewhere they would stretch day-metrics past its cap.
  let fetchRange = $derived.by(() => {
    const firsts = [gridCells[0]?.key, weekKeys[0], anchorKey, agendaDays[0]?.key].filter(
      (k): k is string => k !== undefined
    );
    const lasts = [
      gridCells[gridCells.length - 1]?.key,
      weekKeys[6],
      anchorKey,
      agendaDays[agendaDays.length - 1]?.key,
    ].filter((k): k is string => k !== undefined);
    if (currentView === 'year') {
      firsts.push(`${viewYear}-01-01`);
      lasts.push(`${viewYear}-12-31`);
    }
    return {
      start: firsts.reduce((a, b) => (b < a ? b : a)),
      end: lasts.reduce((a, b) => (b > a ? b : a)),
    };
  });

  // ── Labels ─────────────────────────────────────────────────────────────────
  let weekLabel = $derived.by(() => {
    const first = parseLocalDate(weekKeys[0]);
    const last = parseLocalDate(weekKeys[6]);
    const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
    return `${first.toLocaleDateString($locale, opts)} – ${last.toLocaleDateString($locale, { ...opts, year: 'numeric' })}`;
  });

  let rangeLabel = $derived.by(() => {
    switch (currentView) {
      case 'month':
        return `${$t(`calendar.months.${viewMonth}`)} ${viewYear}`;
      case 'week':
        return weekLabel;
      case 'day':
        return anchorDate.toLocaleDateString($locale, {
          weekday: 'long',
          day: 'numeric',
          month: 'long',
          year: 'numeric',
        });
      case 'agenda':
        return `${$t('calendar.views.agenda')} · ${AGENDA_DAYS} ${$t('calendar.agendaDays')}`;
      case 'year':
        return String(viewYear);
    }
  });

  // ── Navigation ─────────────────────────────────────────────────────────────
  function shiftAnchor(days: number, months: number, years: number): void {
    const d = parseLocalDate(anchorKey);
    const next = new Date(d.getFullYear(), d.getMonth() + months, d.getDate() + days);
    anchorKey = localDayKey(new Date(next.getFullYear() + years, next.getMonth(), next.getDate()));
  }

  function prevRange(): void {
    if (currentView === 'week') shiftAnchor(-7, 0, 0);
    else if (currentView === 'day') shiftAnchor(-1, 0, 0);
    else if (currentView === 'agenda') shiftAnchor(-AGENDA_DAYS, 0, 0);
    else if (currentView === 'year') shiftAnchor(0, 0, -1);
    else shiftAnchor(0, -1, 0);
    void refresh();
  }

  function nextRange(): void {
    if (currentView === 'week') shiftAnchor(7, 0, 0);
    else if (currentView === 'day') shiftAnchor(1, 0, 0);
    else if (currentView === 'agenda') shiftAnchor(AGENDA_DAYS, 0, 0);
    else if (currentView === 'year') shiftAnchor(0, 0, 1);
    else shiftAnchor(0, 1, 0);
    void refresh();
  }

  function goToday(): void {
    anchorKey = currentDayKey();
    todayKey = anchorKey;
    selectedDay = anchorKey;
    void refresh();
  }

  function selectDay(key: string): void {
    selectedDay = selectedDay === key ? null : key;
    // Selecting a day in month view also re-anchors, so day/week views and
    // the mini-month stay in sync.
    anchorKey = key;
  }

  function miniSelectDay(key: string): void {
    selectedDay = key;
    anchorKey = key;
  }

  function jumpToMonth(month: number, dayKey?: string): void {
    const d = dayKey ? parseLocalDate(dayKey) : new Date(viewYear, month, 1);
    anchorKey = localDayKey(new Date(d.getFullYear(), month, d.getDate()));
    setView('month');
  }

  // ── Data ───────────────────────────────────────────────────────────────────
  async function refresh(): Promise<void> {
    try {
      syncToday();
      // The cache stores all-day events at UTC midnight, which in
      // negative-offset zones is an instant on the previous local day —
      // pad the lower bound by one day so those rows are still returned.
      const eventsStart = new Date(`${addDays(fetchRange.start, -1)}T00:00:00`).toISOString();
      const eventsEnd = new Date(`${fetchRange.end}T23:59:59.999`).toISOString();
      const [evts, st, scheduled, unscheduled, metrics] = await Promise.all([
        api.google.calendarEvents({ start: eventsStart, end: eventsEnd }),
        api.google.calendarStatus(),
        api.calendarTasks.list({ start: fetchRange.start, end: fetchRange.end }),
        api.calendarTasks.list({ unscheduled: true }),
        api.calendarTasks.dayMetrics({ start: fetchRange.start, end: fetchRange.end }),
      ]);
      events = evts;
      status = st;
      tasks = [...scheduled, ...unscheduled];
      dayMetrics = metrics;
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

  async function loadAuxiliary(): Promise<void> {
    // Calendars (filter list) + goals (editor linking) are side data —
    // failures must never break the calendar itself.
    try {
      if (status?.connected) googleCalendars = await api.google.calendars();
    } catch (e) {
      logger.warn('Could not load calendar list', e);
    }
    try {
      goals = await api.goals.list();
    } catch (e) {
      logger.warn('Could not load goals for linking', e);
    }
  }

  const AUTO_SYNC_STALE_MS = 15 * 60 * 1000;

  async function sync(silent = false): Promise<void> {
    syncing = true;
    try {
      await api.google.calendarSync();
      if (!silent) showNotification($t('calendar.syncOk'), 'success');
      await refresh();
      await loadAuxiliary();
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

  // ── Calendar visibility filters (#1658) ─────────────────────────────────────
  function toggleCalendar(id: string): void {
    const next = new Set(hiddenCalendarIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    hiddenCalendarIds = next;
    persistPrefs();
  }

  function toggleHeatmap(): void {
    heatmap = !heatmap;
    persistPrefs();
  }

  function toggleMetrics(): void {
    showMetrics = !showMetrics;
    persistPrefs();
  }

  function toggleTray(): void {
    trayCollapsed = !trayCollapsed;
    persistPrefs();
  }

  // ── Google write-back helpers ───────────────────────────────────────────────
  // `hhmm` on `day` plus one real hour, returned as `YYYY-MM-DDTHH:mm:ss`.
  function addHour(day: string, hhmm: string): string {
    const start = new Date(`${day}T${hhmm.slice(0, 5)}:00`);
    const end = new Date(start.getTime() + 3600e3);
    return `${localDayKey(end)}T${pad2(end.getHours())}:${pad2(end.getMinutes())}:00`;
  }

  // Build the Google EventDateTime pair for a task's window. All-day tasks
  // publish `{date}`; Google's end.date is EXCLUSIVE, so it must be the day
  // after — same-day start+end is a zero-length event Google rejects.
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

  function attendeeList(attendees: string | null | undefined): string[] | undefined {
    const list = (attendees ?? '')
      .split(',')
      .map((a) => a.trim())
      .filter(Boolean);
    return list.length > 0 ? list : undefined;
  }

  // ── Task CRUD ──────────────────────────────────────────────────────────────
  async function updateTask(task: CalendarTask, patch: Parameters<typeof api.calendarTasks.update>[1]): Promise<CalendarTask | null> {
    try {
      const updated = await api.calendarTasks.update(task.id, patch);
      tasks = tasks.map((t) => (t.id === updated.id ? updated : t));
      return updated;
    } catch (e) {
      logger.error(e);
      showNotification($t('calendar.taskUpdateError'), 'error');
      return null;
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
      tasks = [...tasks, task];
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

  function cyclePriority(task: CalendarTask): void {
    const idx = PRIORITIES.indexOf(task.priority);
    const next = PRIORITIES[(idx + 1) % PRIORITIES.length];
    void updateTask(task, { priority: next });
  }

  // ── Event editor (#1658) ────────────────────────────────────────────────────
  function openCreateEditor(dayKey?: string | null): void {
    editorMode = 'create';
    editorTask = null;
    editorGoogleEvent = null;
    editorInitialDate = dayKey ?? selectedDay ?? todayKey;
    editorInitialTime = null;
    editorOpen = true;
  }

  function openItem(item: DayItem): void {
    if (item.kind === 'task') {
      editorMode = 'edit-task';
      editorTask = item.task;
      editorGoogleEvent = null;
    } else {
      editorMode = 'edit-google';
      editorTask = null;
      editorGoogleEvent = item.event;
    }
    editorOpen = true;
  }

  function closeEditor(): void {
    editorOpen = false;
    editorTask = null;
    editorGoogleEvent = null;
  }

  async function onEditorSaveTask(payload: EventEditorSave): Promise<void> {
    editorSaving = true;
    try {
      if (editorMode === 'create') {
        if (payload.reminder_minutes !== null) void requestNotificationPermission();
        const created = await api.calendarTasks.create({
          title: payload.title,
          date: payload.date,
          start_time: payload.start_time,
          end_time: payload.end_time,
          priority: payload.priority,
          goal_id: payload.goal_id,
          color: payload.color,
          recurrence: payload.recurrence,
          reminder_minutes: payload.reminder_minutes,
          description: payload.description,
          location: payload.location,
          attendees: payload.attendees,
        });
        tasks = [...tasks, created];
        if (payload.publishToGoogle && status?.connected && payload.date) {
          try {
            const g = await api.google.calendarCreateEvent({
              summary: payload.title,
              ...googleWindow(payload.date, payload.start_time, payload.end_time),
              description: payload.description ?? undefined,
              location: payload.location ?? undefined,
              attendees: attendeeList(payload.attendees),
            });
            const mirrored = await api.calendarTasks.update(created.id, {
              google_event_id: g.google_id,
            });
            tasks = tasks.map((t) => (t.id === mirrored.id ? mirrored : t));
            await refresh();
          } catch (e) {
            logger.warn('Google publish failed', e);
            showNotification($t('calendar.googlePublishError'), 'error');
          }
        }
      } else if (editorTask) {
        if (payload.reminder_minutes !== null) void requestNotificationPermission();
        const updated = await updateTask(editorTask, {
          title: payload.title,
          date: payload.date,
          start_time: payload.start_time,
          end_time: payload.end_time,
          priority: payload.priority,
          goal_id: payload.goal_id,
          color: payload.color,
          recurrence: payload.recurrence,
          reminder_minutes: payload.reminder_minutes,
          description: payload.description,
          location: payload.location,
          attendees: payload.attendees,
        });
        if (updated?.google_event_id && status?.connected && payload.date) {
          try {
            await api.google.calendarUpdateEvent(updated.google_event_id, {
              summary: payload.title,
              ...googleWindow(payload.date, payload.start_time, payload.end_time),
              description: payload.description ?? undefined,
              location: payload.location ?? undefined,
              attendees: attendeeList(payload.attendees),
            });
            await refresh();
          } catch (e) {
            logger.warn('Google update failed', e);
            showNotification($t('calendar.googlePublishError'), 'error');
          }
        }
      }
      closeEditor();
    } catch (e) {
      logger.error(e);
      showNotification($t('calendar.taskUpdateError'), 'error');
    } finally {
      editorSaving = false;
    }
  }

  async function onEditorSaveGoogle(
    event: CalendarEvent,
    patch: GoogleEventSave
  ): Promise<void> {
    editorSaving = true;
    try {
      // GoogleEventSave uses null for "clear"; the PATCH payload wants
      // undefined for "leave unset" (a null would no-op anyway server-side).
      await api.google.calendarUpdateEvent(
        event.google_id,
        {
          summary: patch.summary,
          description: patch.description ?? undefined,
          location: patch.location ?? undefined,
        },
        event.calendar_id
      );
      await refresh();
      closeEditor();
    } catch (e) {
      logger.error(e);
      showNotification($t('calendar.googlePublishError'), 'error');
    } finally {
      editorSaving = false;
    }
  }

  async function onEditorDelete(task: CalendarTask): Promise<void> {
    closeEditor();
    await removeTask(task);
  }

  async function onEditorDuplicate(task: CalendarTask): Promise<void> {
    try {
      const clone = await api.calendarTasks.duplicate(task.id);
      tasks = [...tasks, clone];
      showNotification($t('calendar.editor.duplicated'), 'success');
      closeEditor();
    } catch (e) {
      logger.error(e);
      showNotification($t('calendar.taskUpdateError'), 'error');
    }
  }

  async function onEditorCreateNote(task: CalendarTask): Promise<void> {
    if (task.note_id) {
      closeEditor();
      await goto(`/notes?id=${task.note_id}`);
      return;
    }
    try {
      const lines = [
        `## ${task.title}`,
        '',
        `- ${$t('calendar.editor.date')}: ${task.date ?? '—'}`,
        task.start_time ? `- ${$t('calendar.startTime')}: ${task.start_time.slice(0, 5)}` : null,
        task.location ? `- ${$t('calendar.editor.location')}: ${task.location}` : null,
        '',
        task.description ?? '',
      ].filter((l): l is string => l !== null);
      const note = await api.notes.create({
        title: task.title,
        content: lines.join('\n'),
        tags: ['calendar'],
        source: 'calendar',
      });
      const updated = await api.calendarTasks.update(task.id, { note_id: note.id });
      tasks = tasks.map((t) => (t.id === updated.id ? updated : t));
      if (editorTask?.id === task.id) editorTask = updated;
      showNotification($t('calendar.editor.noteCreated'), 'success');
    } catch (e) {
      logger.error(e);
      showNotification($t('calendar.editor.noteError'), 'error');
    }
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
    void rescheduleTask(task, cellKey);
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
    void unscheduleTask(task);
  }

  async function unscheduleTask(task: CalendarTask): Promise<void> {
    const previousDate = task.date;
    tasks = tasks.map((t) => (t.id === task.id ? { ...t, date: null } : t));
    try {
      const updated = await api.calendarTasks.update(task.id, { date: null });
      tasks = tasks.map((t) => (t.id === updated.id ? updated : t));
      showNotification($t('calendar.taskUnscheduled'), 'success');
    } catch (e) {
      logger.error(e);
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
  // system Notification only when the user granted permission.
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
  let planSuggestions = $state<PlanSuggestion[]>([]);
  let planLoading = $state(false);
  let planApplying = $state(false);
  let planByDay = $derived(planSuggestionsByDay(planSuggestions));

  function planTaskTitle(taskId: number): string {
    return tasks.find((t) => t.id === taskId)?.title ?? `#${taskId}`;
  }

  async function suggestPlan(): Promise<void> {
    if (planLoading) return;
    planLoading = true;
    planSuggestions = [];
    try {
      // Bound by the month grid (~42d): in year view fetchRange spans a full
      // year, which the backend planning cap (62d) would reject.
      const res = await api.ai.planSuggest({
        week_start: gridCells[0].key,
        week_end: gridCells[gridCells.length - 1].key,
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

  // ── Keyboard shortcuts (#1658) ─────────────────────────────────────────────
  function onGlobalKeydown(e: KeyboardEvent): void {
    const el = e.target as HTMLElement | null;
    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable)) return;
    if (editorOpen) return;
    if (e.key === 't' || e.key === 'T') goToday();
    else if (e.key === 'n' || e.key === 'N') openCreateEditor();
    else if (e.key === 'ArrowLeft') prevRange();
    else if (e.key === 'ArrowRight') nextRange();
    else if (e.key === '1') setView('month');
    else if (e.key === '2') setView('week');
    else if (e.key === '3') setView('day');
    else if (e.key === '4') setView('agenda');
    else if (e.key === '5') setView('year');
  }

  onMount(() => {
    void (async () => {
      await refresh();
      await loadAuxiliary();
      await maybeAutoSync();
    })();
    // The 30s reminder poll doubles as the midnight-rollover check: when the
    // day changed, ranges shift so events/tasks must be refetched (#1306).
    const timer = setInterval(() => {
      if (syncToday()) void refresh();
      checkTaskReminders();
    }, 30_000);
    const onVisible = () => {
      if (document.visibilityState === 'visible' && syncToday()) void refresh();
    };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('keydown', onGlobalKeydown);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('keydown', onGlobalKeydown);
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
            values: { when: new Date(status.last_synced_at).toLocaleString($locale) },
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
      <button class="btn btn-ghost" onclick={() => openCreateEditor()}>
        <Plus size={13} />
        {$t('calendar.editor.newEvent')}
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
  {:else if status && !status.connected && googleCalendars.length === 0 && events.length === 0 && tasks.length === 0}
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
    <div class="planner-body">
      <!-- Left rail: mini-month navigator + calendar filters + unscheduled tray -->
      <aside class="planner-rail">
        <MiniMonth
          year={viewYear}
          month={viewMonth}
          {todayKey}
          {selectedDay}
          metricsByDay={metricsMap}
          onSelectDay={miniSelectDay}
          onPrevMonth={() => shiftAnchor(0, -1, 0)}
          onNextMonth={() => shiftAnchor(0, 1, 0)}
        />

        {#if googleCalendars.length > 0}
          <div class="rail-section">
            <span class="rail-title caption">{$t('calendar.myCalendars')}</span>
            <label class="cal-filter">
              <input
                type="checkbox"
                checked={showJoidyTasks}
                onchange={() => (showJoidyTasks = !showJoidyTasks)}
              />
              <span class="cal-dot" style="background: var(--accent);"></span>
              <span class="cal-name">{$t('calendar.joidyTasks')}</span>
            </label>
            {#each googleCalendars as cal (cal.id)}
              <label class="cal-filter">
                <input
                  type="checkbox"
                  checked={!hiddenCalendarIds.has(cal.id)}
                  onchange={() => toggleCalendar(cal.id)}
                />
                <span
                  class="cal-dot"
                  style="background: {cal.backgroundColor ?? 'var(--text-muted)'};"
                ></span>
                <span class="cal-name">{cal.summary ?? cal.id}</span>
              </label>
            {/each}
          </div>
        {/if}

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
                    <button
                      class="tray-task-open"
                      onclick={() =>
                        openItem({
                          kind: 'task',
                          id: `t-${task.id}`,
                          label: task.title,
                          time: null,
                          allDay: true,
                          startMin: null,
                          endMin: null,
                          color: task.color,
                          location: task.location,
                          description: task.description,
                          task,
                        })}
                    >
                      <span class="priority-dot {priorityClass(task.priority)}"></span>
                      {#if task.recurrence !== 'NONE'}<Repeat size={10} class="recur-icon" />{/if}
                      <span class="tray-task-title">{task.title}</span>
                    </button>
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
      </aside>

      <!-- Main view card -->
      <div class="calendar-card">
        <div class="calendar-toolbar">
          <button
            class="btn btn-ghost nav-btn"
            onclick={prevRange}
            aria-label={$t('calendar.prevRange')}
          >
            <ChevronLeft size={16} />
          </button>
          <span class="month-label">{rangeLabel}</span>
          <button
            class="btn btn-ghost nav-btn"
            onclick={nextRange}
            aria-label={$t('calendar.nextRange')}
          >
            <ChevronRight size={16} />
          </button>
          <button class="btn btn-ghost nav-btn" onclick={goToday}>{$t('calendar.today')}</button>

          <div class="search-box">
            <Search size={12} class="search-icon" />
            <input
              class="input search-input"
              type="search"
              bind:value={searchQuery}
              placeholder={$t('calendar.searchPlaceholder')}
              aria-label={$t('calendar.searchPlaceholder')}
            />
          </div>

          <button
            class="btn btn-ghost nav-btn"
            class:toggled={heatmap}
            onclick={toggleHeatmap}
            title={$t('calendar.heatmapHint')}
            aria-pressed={heatmap}
            aria-label={$t('calendar.heatmap')}
          >
            <Flame size={14} />
          </button>
          <button
            class="btn btn-ghost nav-btn"
            class:toggled={!showMetrics}
            onclick={toggleMetrics}
            title={$t('calendar.metricsToggleHint')}
            aria-pressed={showMetrics}
            aria-label={$t('calendar.metricsToggle')}
          >
            <EyeOff size={14} />
          </button>
          <button
            class="btn btn-ghost nav-btn plan-btn"
            onclick={suggestPlan}
            disabled={planLoading}
            title={$t('calendar.planSuggestHint')}
            aria-label={$t('calendar.planSuggest')}
          >
            <Sparkles size={14} class={planLoading ? 'spin' : ''} />
          </button>
        </div>

        {#if currentView === 'month'}
          <MonthGrid
            cells={gridCells}
            {itemsByDay}
            metricsByDay={metricsMap}
            {planByDay}
            {todayKey}
            {selectedDay}
            {dropTargetKey}
            draggedTaskId={draggedTask?.id ?? null}
            {heatmap}
            {showMetrics}
            onSelectDay={selectDay}
            onOpenItem={openItem}
            onTaskDragStart={onChipDragStart}
            onTaskDragEnd={onChipDragEnd}
            onCellDragOver={onCellDragOver}
            onCellDragLeave={onCellDragLeave}
            onCellDrop={onCellDrop}
            onAcceptSuggestion={acceptSuggestion}
            taskTitle={planTaskTitle}
          />
        {:else if currentView === 'week'}
          <TimeGrid
            columns={weekKeys.map((key) => ({
              key,
              label: `${$t(`calendar.weekDays.${(parseLocalDate(key).getDay() + 6) % 7}`)} ${parseLocalDate(key).getDate()}`,
            }))}
            {itemsByDay}
            metricsByDay={metricsMap}
            {planByDay}
            {todayKey}
            {selectedDay}
            {dropTargetKey}
            draggedTaskId={draggedTask?.id ?? null}
            {showMetrics}
            onSelectDay={selectDay}
            onOpenItem={openItem}
            onTaskDragStart={onChipDragStart}
            onTaskDragEnd={onChipDragEnd}
            onCellDragOver={onCellDragOver}
            onCellDragLeave={onCellDragLeave}
            onCellDrop={onCellDrop}
            onAcceptSuggestion={acceptSuggestion}
            taskTitle={planTaskTitle}
          />
        {:else if currentView === 'day'}
          <TimeGrid
            columns={[{ key: anchorKey, label: rangeLabel }]}
            {itemsByDay}
            metricsByDay={metricsMap}
            {planByDay}
            {todayKey}
            {selectedDay}
            {dropTargetKey}
            draggedTaskId={draggedTask?.id ?? null}
            {showMetrics}
            onSelectDay={selectDay}
            onOpenItem={openItem}
            onTaskDragStart={onChipDragStart}
            onTaskDragEnd={onChipDragEnd}
            onCellDragOver={onCellDragOver}
            onCellDragLeave={onCellDragLeave}
            onCellDrop={onCellDrop}
            onAcceptSuggestion={acceptSuggestion}
            taskTitle={planTaskTitle}
          />
        {:else if currentView === 'agenda'}
          <AgendaList
            days={agendaDays}
            metricsByDay={metricsMap}
            {planByDay}
            {todayKey}
            {selectedDay}
            {showMetrics}
            onSelectDay={selectDay}
            onOpenItem={openItem}
            onAcceptSuggestion={acceptSuggestion}
            taskTitle={planTaskTitle}
          />
        {:else if currentView === 'year'}
          <YearGrid
            year={viewYear}
            {todayKey}
            {selectedDay}
            metricsByDay={metricsMap}
            onSelectDay={(key) => {
              selectedDay = key;
              jumpToMonth(parseLocalDate(key).getMonth(), key);
            }}
            onJumpToMonth={jumpToMonth}
          />
        {/if}
      </div>

      <!-- Day detail panel -->
      <aside class="day-detail">
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
            {parseLocalDate(selectedDay).toLocaleDateString($locale, {
              weekday: 'long',
              day: 'numeric',
              month: 'long',
            })}
          </h4>
          {#if showMetrics && selectedDayMetrics}
            <div class="metrics-detail">
              <DayBadges metrics={selectedDayMetrics} compact={false} />
              <span class="caption metrics-line">
                {$t('calendar.metrics.detail', {
                  values: {
                    focus: selectedDayMetrics.focus_minutes,
                    pomodoros: selectedDayMetrics.pomodoros,
                    xp: selectedDayMetrics.xp,
                    notes: selectedDayMetrics.notes,
                    goals: selectedDayMetrics.goals_completed,
                  },
                })}
              </span>
            </div>
          {/if}
          {#if selectedDayItems.length === 0}
            <span class="caption">{$t('calendar.noEventsDay')}</span>
          {:else}
            <div class="event-list">
              {#each selectedDayItems as item (item.kind === 'google' ? `g-${item.id}` : `t-${item.task.id}`)}
                {#if item.kind === 'google'}
                  <button class="event-item" onclick={() => openItem(item)}>
                    <span class="event-time caption"
                      >{item.allDay ? $t('calendar.allDay') : item.time}</span
                    >
                    <span class="event-summary"
                      ><Lock size={10} class="lock-icon" /> {item.label}</span
                    >
                    {#if item.location}
                      <span class="event-location caption"><MapPin size={9} /> {item.location}</span>
                    {/if}
                  </button>
                {:else}
                  <div class="event-item task-item" class:done={item.task.done}>
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
                    <button class="event-summary event-open" onclick={() => openItem(item)}>
                      {#if item.task.recurrence !== 'NONE'}<Repeat size={10} class="recur-icon" />{/if}
                      {item.task.title}
                      {#if item.task.note_id}<NotebookPen size={10} class="lock-icon" />{/if}
                    </button>
                    <span class="task-actions">
                      <button
                        class="btn btn-ghost icon-btn"
                        onclick={() => openItem(item)}
                        aria-label={$t('calendar.edit')}
                      >
                        <NotebookPen size={12} />
                      </button>
                      <button
                        class="btn btn-ghost icon-btn"
                        onclick={() => removeTask(item.task)}
                        aria-label={$t('calendar.delete')}
                      >
                        <Trash2 size={12} />
                      </button>
                    </span>
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
            <button
              type="submit"
              class="btn btn-icon quick-submit"
              disabled={addingTask || !quickAddTitle.trim()}
              aria-label={$t('calendar.addTask')}
            >
              <Plus size={14} />
            </button>
          </form>
          <button class="btn btn-ghost full-editor-btn" onclick={() => openCreateEditor()}>
            <Plus size={12} />
            {$t('calendar.editor.openFull')}
          </button>
        {:else}
          <h4>{$t('calendar.pickDay')}</h4>
          <span class="caption">{$t('calendar.pickDayHint')}</span>
        {/if}
      </aside>
    </div>

    <EventEditor
      open={editorOpen}
      mode={editorMode}
      task={editorTask}
      googleEvent={editorGoogleEvent}
      initialDate={editorInitialDate}
      initialTime={editorInitialTime}
      {goals}
      connected={status?.connected ?? false}
      saving={editorSaving}
      onClose={closeEditor}
      onSaveTask={onEditorSaveTask}
      onSaveGoogle={onEditorSaveGoogle}
      onDelete={onEditorDelete}
      onDuplicate={onEditorDuplicate}
      onCreateNote={onEditorCreateNote}
    />
  {/if}
</div>

<style>
  .calendar-page {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 1400px;
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

  .planner-body {
    display: grid;
    grid-template-columns: 200px 1fr minmax(260px, 320px);
    gap: 12px;
    flex: 1;
    min-height: 0;
  }

  .planner-rail {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 0;
    overflow-y: auto;
  }

  .rail-section {
    display: flex;
    flex-direction: column;
    gap: 4px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s2);
  }

  .rail-title {
    font-weight: 600;
    padding: 0 4px 2px;
  }

  .cal-filter {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 4px;
  }

  .cal-filter:hover {
    background: var(--hover);
  }

  .cal-filter input {
    margin: 0;
    accent-color: var(--accent);
  }

  .cal-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .cal-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .calendar-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3);
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
  }

  .calendar-toolbar {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: var(--s2);
    flex-shrink: 0;
    flex-wrap: wrap;
  }

  .month-label {
    flex: 0 1 auto;
    min-width: 120px;
    text-align: center;
    font-weight: 600;
    font-size: 13px;
    text-transform: capitalize;
  }

  .nav-btn {
    padding: 4px 8px;
  }

  .nav-btn.toggled {
    color: var(--xp);
    background: color-mix(in srgb, var(--xp) 14%, transparent);
  }

  .search-box {
    position: relative;
    display: flex;
    align-items: center;
    margin-left: auto;
  }

  .search-box :global(.search-icon) {
    position: absolute;
    left: 7px;
    color: var(--text-muted);
    pointer-events: none;
  }

  .search-input {
    font-size: 11px;
    padding: var(--s1) var(--s2) var(--s1) 22px;
    width: 170px;
  }

  .plan-btn {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  /* Unscheduled tray ("sin planificar", #1234) */
  .unscheduled-tray {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s2);
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
    transition: border-color var(--t-fast) ease;
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
    font-size: 11px;
    font-weight: 600;
  }

  .tray-chevron {
    transition: transform var(--t-fast) ease;
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
    gap: 4px;
  }

  .tray-add-input {
    flex: 1;
    min-width: 0;
    padding: var(--s1) var(--s2);
    font-size: 11px;
  }

  .tray-empty {
    font-style: italic;
    opacity: 0.6;
    padding: 0 4px;
  }

  .tray-items {
    display: flex;
    flex-direction: column;
    gap: 4px;
    overflow-y: auto;
    min-height: 0;
    max-height: 220px;
  }

  .tray-task {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 3px 6px;
    border: 1px solid var(--border);
    border-radius: calc(var(--r) * 0.6);
    background: var(--surface-2, rgba(255, 255, 255, 0.02));
    font-size: 11px;
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

  .tray-task-open {
    display: flex;
    align-items: center;
    gap: 5px;
    flex: 1;
    min-width: 0;
    background: none;
    border: none;
    color: inherit;
    cursor: pointer;
    padding: 0;
    font-size: inherit;
    text-align: left;
  }

  .tray-task-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tray-task .icon-btn {
    margin-left: auto;
  }

  .priority-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
    background: currentColor;
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

  .lock-icon,
  .recur-icon {
    flex-shrink: 0;
    opacity: 0.6;
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

  .metrics-detail {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: 6px 8px;
    border: 1px solid var(--border);
    border-radius: calc(var(--r) * 0.6);
    background: var(--surface-2, rgba(255, 255, 255, 0.02));
  }

  .metrics-line {
    font-variant-numeric: tabular-nums;
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
    background: transparent;
    color: inherit;
    cursor: pointer;
    text-align: left;
    width: 100%;
    font-size: inherit;
  }

  .event-item:hover {
    background: var(--hover);
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

  .event-open {
    background: none;
    border: none;
    color: inherit;
    cursor: pointer;
    padding: 0;
    font-size: inherit;
    text-align: left;
    flex: 1;
  }

  .event-open:hover {
    color: var(--xp);
  }

  .event-location {
    margin-left: auto;
    text-align: right;
    display: inline-flex;
    align-items: center;
    gap: 3px;
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
    flex-wrap: wrap;
  }

  .quick-input {
    flex: 1;
    min-width: 120px;
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

  .full-editor-btn {
    font-size: 11px;
    align-self: flex-start;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .empty-wrap {
    padding: var(--s4) 0;
  }

  .spin {
    animation: spin 1s linear infinite;
    display: inline-flex;
  }

  /* AI plan suggestions (#1237) */
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

  @media (max-width: 1000px) {
    .planner-body {
      grid-template-columns: 1fr minmax(260px, 320px);
    }

    .planner-rail {
      display: none;
    }
  }

  @media (max-width: 640px) {
    .planner-body {
      grid-template-columns: 1fr;
      grid-template-rows: minmax(0, 3fr) minmax(0, 2fr);
    }

    .event-location {
      display: none;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .spin {
      animation: none;
    }

    .tray-chevron {
      transition: none;
    }
  }
</style>
