<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import { goto, replaceState } from '$app/navigation';
  import { resolve } from '$app/paths';
  import {
    api,
    type CalendarEvent,
    type CalendarTask,
    type CalendarTaskPriority,
    type CalendarTaskRecurrence,
    type Goal,
    type Note,
    type PersonalStreak,
    type PlanSuggestion,
  } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import { loadPref, savePref } from '$lib/utils/persistedState';
  import { locale } from '$lib/stores/locale';
  import { parseLocalDate } from '$lib/utils/date';
  import { showNotification } from '$lib/stores/notifications';
  import {
    dueTaskReminders,
    fireTaskNotification,
    requestNotificationPermission,
  } from '$lib/utils/taskReminders';
  import PlanningCalendar, {
    type CalendarDayBadge,
    type CalendarDayChip,
  } from '$lib/components/calendar/PlanningCalendar.svelte';
  import CalendarLayerToggles from '$lib/components/calendar/CalendarLayerToggles.svelte';
  import {
    CHIP_DENSITY_LIMITS,
    agendaDaysFor,
    assignedIdsForDate,
    calendarLayers,
    chipDensity,
    goPlanningToday,
    jumpToPlanningDay,
    loadAssignmentsForRange,
    monthCellsFor,
    planningAssignments,
    planningCursor,
    planningSelectedDay,
    planningView,
    selectPlanningDay,
    setPlanningView,
    shiftPlanningPeriod,
    weekDaysFor,
  } from '$lib/stores/planningCalendar';
  import ChevronLeft from 'lucide-svelte/icons/chevron-left';
  import ChevronRight from 'lucide-svelte/icons/chevron-right';
  import ChevronDown from 'lucide-svelte/icons/chevron-down';
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
  import Target from 'lucide-svelte/icons/target';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import GoalFromEventModal, { type GoalEventSeed } from '$lib/components/GoalFromEventModal.svelte';
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
        description?: string | null;
        allDay: boolean;
        color: string | null;
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

  // View mode, cursor and day selection live in the shared planning-calendar
  // store (#1660) — Goals → Planificación reads/writes the same state. View
  // persists under `calendarUi` in user settings AND the device-level
  // `joidy.calendar.*` view prefs; cursor and selected day restore from
  // those keys too (#1673), all hydrated by the store.
  let selectedDay = $derived($planningSelectedDay);

  // Quick-add state
  let quickAddTitle = $state('');
  let quickAddTime = $state('');
  let quickAddPriority = $state<CalendarTaskPriority>('MEDIUM');
  let quickAddRecurrence = $state<CalendarTaskRecurrence>('NONE');
  let quickAddReminder = $state<number | null>(null);
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
    if ($planningSelectedDay === prev) selectPlanningDay(next);
    return true;
  }

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

  // A task mirrored to Google (google_event_id) renders as the editable
  // task chip only — skip its cached read-only Google copy so it doesn't
  // appear twice on the same day.
  let mirroredGoogleIds = $derived(
    new Set(tasks.map((t) => t.google_event_id).filter((id): id is string => id !== null))
  );

  // Per-day items (Google events + calendar_tasks), honoring the layer
  // toggles — feeds the day-detail panel; chipsForDay() projects the same
  // data plus planning goals and AI suggestions into the shared grid (#1660).
  function dayItems(iso: string): DayItem[] {
    const items: DayItem[] = [];
    if ($calendarLayers.google) {
      for (const ev of monthEvents.get(iso) ?? []) {
        if (mirroredGoogleIds.has(ev.google_id)) continue;
        items.push({
          kind: 'google',
          id: ev.google_id,
          time: ev.all_day ? null : dtFormatter.format(new Date(ev.start_at)),
          label: ev.summary || '—',
          location: ev.location,
          description: ev.description,
          allDay: ev.all_day,
          color: ev.color,
        });
      }
    }
    if ($calendarLayers.tasks) {
      for (const task of monthTasks.get(iso) ?? []) {
        items.push({
          kind: 'task',
          time: task.start_time ? task.start_time.slice(0, 5) : null,
          label: task.title,
          task,
        });
      }
    }
    items.sort((a, b) => (a.time ?? '99:99').localeCompare(b.time ?? '99:99'));
    return items;
  }

  let selectedDayItems = $derived(selectedDay ? dayItems(selectedDay) : []);

  // Google event → quick goal creation (#goal-from-event)
  let goalFromEventSeed = $state<GoalEventSeed | null>(null);

  // Unscheduled queue ("sin planificar", #1234): tasks with no date.
  let unscheduledTasks = $derived(
    tasks.filter((t) => t.date === null).sort((a, b) => a.created_at.localeCompare(b.created_at))
  );
  let trayCollapsed = $state(
    loadPref<boolean>('calendar', 'trayCollapsed', false, {
      legacyKey: 'joidy-calendar-tray-collapsed',
      legacyFrom: (raw) => raw === '1',
      isValid: (v) => typeof v === 'boolean',
    })
  );
  let trayAddTitle = $state('');
  let trayAdding = $state(false);

  function toggleTray(): void {
    trayCollapsed = !trayCollapsed;
  }

  // Every day currently reachable by the shared grid (month + week + agenda
  // windows around the cursor) — bounds the events/tasks fetch and the
  // assignment prefetch. ISO keys sort lexicographically.
  let visibleDays = $derived.by(() => {
    const days = new Set<string>();
    for (const c of monthCellsFor($planningCursor)) days.add(c.iso);
    for (const d of weekDaysFor($planningCursor)) days.add(d);
    for (const d of agendaDaysFor($planningCursor)) days.add(d);
    return [...days].sort();
  });

  let fetchRange = $derived({
    start: visibleDays[0],
    end: visibleDays[visibleDays.length - 1],
  });

  // Toolbar period label, matching the three view modes.
  let periodLabel = $derived.by(() => {
    if ($planningView === 'month') {
      const d = parseLocalDate($planningCursor);
      return `${$t(`calendar.months.${d.getMonth()}`)} ${d.getFullYear()}`;
    }
    if ($planningView === 'week') {
      const days = weekDaysFor($planningCursor);
      const first = parseLocalDate(days[0]);
      const last = parseLocalDate(days[6]);
      const firstMonth = $t(`calendar.months.${first.getMonth()}`);
      const lastMonth = $t(`calendar.months.${last.getMonth()}`);
      const firstYear = days[0].slice(0, 4);
      const lastYear = days[6].slice(0, 4);
      if (firstMonth === lastMonth) {
        return `${first.getDate()} - ${last.getDate()} ${firstMonth} ${firstYear}`;
      }
      const firstPart =
        firstYear !== lastYear
          ? `${first.getDate()} ${firstMonth} ${firstYear}`
          : `${first.getDate()} ${firstMonth}`;
      return `${firstPart} - ${last.getDate()} ${lastMonth} ${lastYear}`;
    }
    return `${$t('calendar.views.agenda')} (14 ${$t('calendar.agendaDays')})`;
  });

  // The unscheduled tray is page-local chrome — its collapse pref lives in
  // the `joidy.calendar.*` device-level namespace (#1673); view, cursor and
  // selected day persist through the shared store.
  $effect(() => {
    savePref('calendar', 'trayCollapsed', trayCollapsed);
  });

  function prevRange(): void {
    shiftPlanningPeriod(-1);
    void refresh();
  }

  function nextRange(): void {
    shiftPlanningPeriod(1);
    void refresh();
  }

  function goToday(): void {
    goPlanningToday();
    todayKey = currentDayKey();
    void refresh();
  }

  // ── Shared-grid projection (#1660) ───────────────────────────────────────
  // Flatten every data source into CalendarDayChip/CalendarDayBadge — the
  // component owns layout, density overflow ("+N more") and drag plumbing.

  let goals = $state<Goal[]>([]);
  let goalsFetched = $state(false);
  let goalsById = $derived(new Map(goals.map((g) => [g.id, g])));

  // Planning layer: goal list is fetched lazily the first time the layer is
  // on — goal chips need titles/colors the assignment cache doesn't carry.
  $effect(() => {
    if (!$calendarLayers.planning || goalsFetched) return;
    goalsFetched = true;
    api.goals
      .list(0, 500)
      .then((list) => (goals = list))
      .catch((e) => {
        goalsFetched = false;
        logger.error('[calendar] goals fetch failed:', e);
      });
  });

  $effect(() => {
    if (!$calendarLayers.planning) return;
    loadAssignmentsForRange(visibleDays).catch(logger.error);
  });

  // Streaks layer: check-in state as day-cell badges, lazily fetched.
  let streaks = $state<PersonalStreak[]>([]);
  let streaksFetched = $state(false);
  $effect(() => {
    if (!$calendarLayers.streaks || streaksFetched) return;
    streaksFetched = true;
    api.personalStreaks
      .list()
      .then((list) => (streaks = list))
      .catch((e) => {
        streaksFetched = false;
        logger.error('[calendar] streaks fetch failed:', e);
      });
  });

  // Notes layer: count badge per day, lazily fetched.
  let calendarNotes = $state<Note[]>([]);
  let notesFetched = $state(false);
  $effect(() => {
    if (!$calendarLayers.notes || notesFetched) return;
    notesFetched = true;
    api.notes
      .list()
      .then((list) => (calendarNotes = list))
      .catch((e) => {
        notesFetched = false;
        logger.error('[calendar] notes fetch failed:', e);
      });
  });

  let notesCountByDay = $derived.by(() => {
    const byDay = new Map<string, number>();
    for (const note of calendarNotes) {
      const key = note.created_at.slice(0, 10);
      byDay.set(key, (byDay.get(key) ?? 0) + 1);
    }
    return byDay;
  });

  function chipsForDay(iso: string): CalendarDayChip[] {
    const layers = $calendarLayers;
    const assigned = layers.planning
      ? assignedIdsForDate($planningAssignments, iso)
      : [];
    const assignedSet = new Set(assigned);
    const chips: CalendarDayChip[] = [];

    // AI ghost proposals render first so the density overflow can never
    // hide them behind "+N more" (#1237).
    for (const sugg of planByDay.get(iso) ?? []) {
      chips.push({
        key: `sg-${sugg.task_id}-${sugg.date}`,
        kind: 'suggestion',
        label: planTaskTitle(sugg.task_id),
        time: sugg.start_time.slice(0, 5),
        ghost: true,
        title: sugg.rationale || $t('calendar.planAcceptHint'),
        payload: sugg,
      });
    }

    for (const item of dayItems(iso)) {
      if (item.kind === 'google') {
        chips.push({
          key: `g-${item.id}`,
          kind: 'google',
          label: item.label,
          time: item.time,
          allDay: item.allDay,
          locked: true,
          color: item.color ?? undefined,
          title: item.location ? `${item.label} · ${item.location}` : item.label,
          payload: item,
        });
      } else {
        // A task mirrored from a planning assignment (goal_id assigned to a
        // bucket this date belongs to) renders as the goal chip only (#1234).
        if (
          layers.planning &&
          item.task.goal_id != null &&
          assignedSet.has(item.task.goal_id)
        ) {
          continue;
        }
        chips.push({
          key: `t-${item.task.id}`,
          kind: 'task',
          label: item.label,
          time: item.time,
          priority: item.task.priority,
          done: item.task.done,
          recurring: item.task.recurrence !== 'NONE',
          draggable: true,
          color: item.task.color ?? undefined,
          title: taskChipTitle(item.task),
          payload: item.task,
        });
      }
    }

    for (const id of assigned) {
      const goal = goalsById.get(id);
      if (!goal) continue;
      chips.push({
        key: `goal-${id}-${iso}`,
        kind: 'goal',
        label: goal.title,
        color: goal.color ?? 'var(--accent)',
        title: goal.title,
        payload: goal,
      });
    }
    return chips;
  }

  function badgesForDay(iso: string): CalendarDayBadge[] {
    const layers = $calendarLayers;
    const badges: CalendarDayBadge[] = [];
    if (layers.streaks) {
      for (const streak of streaks) {
        if (streak.is_archived) continue;
        const entry = streak.history?.find((h) => h.date === iso);
        badges.push({
          key: `s-${streak.id}`,
          kind: 'streak',
          icon: streak.icon || streak.emoji,
          color: streak.color || 'var(--xp)',
          checked: entry?.checked ?? false,
          title: streak.name,
        });
      }
    }
    if (layers.notes) {
      const count = notesCountByDay.get(iso) ?? 0;
      if (count > 0) {
        badges.push({
          key: 'notes',
          kind: 'note',
          count,
          title: $t('calendar.layer.notes'),
        });
      }
    }
    return badges;
  }

  function onSelectDay(iso: string): void {
    selectPlanningDay($planningSelectedDay === iso ? null : iso);
  }

  function onChipClick(chip: CalendarDayChip, iso: string): void {
    if (chip.kind === 'suggestion' && chip.payload) {
      void acceptSuggestion(chip.payload as PlanSuggestion);
      return;
    }
    // Task/google/goal chips behave like a cell click — select the day and
    // let the detail panel show the actionable list.
    onSelectDay(iso);
  }

  // Goals assigned to the selected day (planning layer detail).
  let selectedDayGoals = $derived.by(() => {
    if (!selectedDay || !$calendarLayers.planning) return [];
    return assignedIdsForDate($planningAssignments, selectedDay)
      .map((id) => goalsById.get(id))
      .filter((g): g is Goal => Boolean(g));
  });

  // Deep-jump into Goals → Planificación; the shared store carries the
  // selection across navigation (#1660).
  function openInGoals(): void {
    void goto('/goals?tab=planning');
  }

  // Tooltip for task chips: surfaces the linked goal so the
  // goals → planning → calendar chain is visible (#goal-planning-calendar).
  function taskChipTitle(task: CalendarTask): string {
    return task.goal_title ? `${task.title} · ${task.goal_title}` : task.title;
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

  function addDays(dayKey: string, days: number): string {
    // Anchor at local noon so adding days across a DST transition stays
    // stable.
    const d = new Date(`${dayKey}T12:00:00`);
    d.setDate(d.getDate() + days);
    return localDayKey(d);
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
      // The backend removes the mirrored Google event on delete.
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
    editingTaskId = null;
  }

  // ── Drag & drop between days (#1236) ──────────────────────────────────────
  let draggedTask = $state<CalendarTask | null>(null);
  let dropTargetKey = $state<string | null>(null);

  function startTaskDrag(event: DragEvent, task: CalendarTask): void {
    draggedTask = task;
    event.dataTransfer?.setData('text/plain', String(task.id));
    if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
  }

  function onChipDragStart(event: DragEvent, chip: CalendarDayChip): void {
    if (chip.kind !== 'task' || !chip.payload) return;
    startTaskDrag(event, chip.payload as CalendarTask);
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

  function onCellDragLeave(_event: DragEvent, cellKey: string): void {
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
    // The backend re-syncs the mirrored Google event on the PATCH.
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

  // Google/joidy color accent for chips and pills: a translucent wash of the
  // real calendar color plus a solid left bar — reads on light and dark
  // surfaces without hardcoding a palette.
  function colorChipStyle(color: string | null | undefined): string {
    if (!color) return '';
    return `background:${color}26;box-shadow:inset 2px 0 0 ${color};`;
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

  // Quick-nav to Goals → Planificación on the selected day (#1668). The date
  // is carried in the query param; the goals page consumes it on mount.
  function openInPlanning(): void {
    void goto(resolve(`/goals?tab=planning&date=${selectedDay ?? todayKey}`));
  }

  // Deep-link support: /calendar?date=YYYY-MM-DD (from Goals → Planificación,
  // #1668). The param is consumed once so manual navigation isn't overridden.
  // Cursor + selection live in the shared store — a jump re-anchors every
  // view (month, week, agenda) so the requested day is in the window.
  function focusDay(key: string): void {
    jumpToPlanningDay(key);
    void refresh();
  }

  $effect(() => {
    const dateParam = page.url.searchParams.get('date');
    if (dateParam && /^\d{4}-\d{2}-\d{2}$/.test(dateParam)) {
      focusDay(dateParam);
      const clean = new URL(page.url.href);
      clean.searchParams.delete('date');
      // eslint-disable-next-line svelte/no-navigation-without-resolve -- page.url.pathname already includes the base path; resolve() would prepend it twice
      replaceState(`${clean.pathname}${clean.search}${clean.hash}`, page.state);
    }
  });

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
              class:active={$planningView === 'month'}
              aria-pressed={$planningView === 'month'}
              onclick={() => setPlanningView('month')}>{$t('calendar.views.month')}</button
            >
            <button
              class="btn btn-ghost view-btn"
              class:active={$planningView === 'week'}
              aria-pressed={$planningView === 'week'}
              onclick={() => setPlanningView('week')}>{$t('calendar.views.week')}</button
            >
            <button
              class="btn btn-ghost view-btn"
              class:active={$planningView === 'agenda'}
              aria-pressed={$planningView === 'agenda'}
              onclick={() => setPlanningView('agenda')}>{$t('calendar.views.agenda')}</button
            >
          </div>

          {#if $planningView !== 'agenda'}
            <button
              class="btn btn-ghost nav-btn"
              onclick={prevRange}
              aria-label={$planningView === 'week'
                ? $t('calendar.prevWeek')
                : $t('calendar.prevMonth')}
            >
              <ChevronLeft size={16} />
            </button>
          {/if}

          <span class="month-label">{periodLabel}</span>

          <button class="btn btn-ghost nav-btn" onclick={goToday}>{$t('calendar.today')}</button>

          {#if $planningView !== 'agenda'}
            <button
              class="btn btn-ghost nav-btn"
              onclick={nextRange}
              aria-label={$planningView === 'week'
                ? $t('calendar.nextWeek')
                : $t('calendar.nextMonth')}
            >
              <ChevronRight size={16} />
            </button>
          {/if}

          <CalendarLayerToggles />

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

          <button
            class="btn btn-ghost nav-btn"
            onclick={openInPlanning}
            title={$t('calendar.openInPlanning')}
            aria-label={$t('calendar.openInPlanning')}
          >
            <Target size={14} />
          </button>
        </div>

        <PlanningCalendar
          view={$planningView}
          cursor={$planningCursor}
          todayIso={todayKey}
          selectedDay={$planningSelectedDay}
          chipsForDay={chipsForDay}
          badgesForDay={badgesForDay}
          maxChips={CHIP_DENSITY_LIMITS[$chipDensity]}
          dropTargetKey={dropTargetKey}
          draggingChipKey={draggedTask ? `t-${draggedTask.id}` : null}
          onselectday={onSelectDay}
          onchipclick={onChipClick}
          oncelldragover={onCellDragOver}
          oncelldragleave={onCellDragLeave}
          oncelldrop={onCellDrop}
          onchipdragstart={onChipDragStart}
          onchipdragend={onChipDragEnd}
        />

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
            {new Date(`${selectedDay}T12:00:00`).toLocaleDateString($locale, {
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
                  <div class="event-item" style={colorChipStyle(item.color)}>
                    <span class="event-time caption"
                      >{item.allDay ? $t('calendar.allDay') : item.time}</span
                    >
                    <span class="event-summary"
                      ><Lock size={10} class="lock-icon" /> {item.label}</span
                    >
                    {#if item.location}
                      <span class="event-location caption">{item.location}</span>
                    {/if}
                    {#if selectedDay}
                      <button
                        type="button"
                        class="event-goal-btn"
                        title={$t('goalFromEvent.action')}
                        aria-label={$t('goalFromEvent.action')}
                        onclick={() =>
                          (goalFromEventSeed = {
                            title: item.label,
                            description: item.description ?? null,
                            location: item.location ?? null,
                            color: item.color,
                            day: selectedDay!,
                            eventId: item.id,
                          })}
                      >
                        <Target size={11} />
                      </button>
                    {/if}
                  </div>
                {:else}
                  <div
                    class="event-item task-item"
                    class:done={item.task.done}
                    style={editingTaskId === item.task.id ? '' : colorChipStyle(item.task.color)}
                  >
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
                      {#if item.task.goal_title}
                        <span class="goal-tag" title={item.task.goal_title}
                          ><Target size={9} />{item.task.goal_title}</span
                        >
                      {/if}
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

          {#if selectedDayGoals.length > 0}
            <div class="planning-assigned">
              <span class="caption planning-assigned-title"
                ><Target size={11} />{$t('calendar.assignedGoals')}</span
              >
              {#each selectedDayGoals as goal (goal.id)}
                <div
                  class="planning-goal"
                  style="border-left: 3px solid {goal.color ?? 'var(--accent)'}"
                >
                  <span class="planning-goal-title">{goal.title}</span>
                </div>
              {/each}
              <button class="btn btn-ghost planning-link" onclick={openInGoals}
                >{$t('calendar.openInGoals')}</button
              >
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
                ondragstart={(e) => startTaskDrag(e, task)}
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

{#if goalFromEventSeed}
  <GoalFromEventModal
    event={goalFromEventSeed}
    onClose={() => (goalFromEventSeed = null)}
  />
{/if}

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
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: var(--s2);
    flex-shrink: 0;
  }

  .month-label {
    flex: 1;
    text-align: center;
    font-weight: 600;
    min-width: 140px;
  }

  .nav-btn {
    padding: 4px 8px;
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

  .event-goal-btn {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    padding: 3px;
    border: none;
    border-radius: var(--r);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    flex-shrink: 0;
  }

  .event-goal-btn:hover {
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
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

  .goal-tag {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    flex-shrink: 1;
    min-width: 0;
    max-width: 40%;
    color: var(--link);
    font-size: 11px;
    font-weight: 400;
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

  /* Planning-assigned goals inside the day detail (#1660) */
  .planning-assigned {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding-top: var(--s2);
    border-top: 1px solid var(--border);
  }

  .planning-assigned-title {
    display: flex;
    align-items: center;
    gap: 5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .planning-goal {
    padding: 6px 8px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    font-size: 12px;
    min-width: 0;
  }

  .planning-goal-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .planning-link {
    align-self: flex-start;
    font-size: 11px;
    padding: 3px 8px;
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
