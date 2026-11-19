<script lang="ts">
  import { onMount } from 'svelte';
  import { api, type CalendarEvent, type CalendarTask, type CalendarTaskPriority } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import { showNotification } from '$lib/stores/notifications';
  import {
    ChevronLeft,
    ChevronRight,
    CalendarDays,
    RefreshCw,
    Settings,
    Lock,
    Plus,
    Trash2,
    Pencil,
    X,
    Check,
  } from 'lucide-svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { t } from 'svelte-i18n';

  interface CalendarStatus {
    connected: boolean;
    calendars: number;
    cached_events: number;
    last_synced_at: string | null;
  }

  type DayItem =
    | { kind: 'google'; time: string | null; label: string; location?: string | null; allDay: boolean }
    | { kind: 'task'; time: string | null; label: string; task: CalendarTask };

  const PRIORITIES: CalendarTaskPriority[] = ['LOW', 'MEDIUM', 'HIGH', 'URGENT'];

  let events: CalendarEvent[] = $state([]);
  let tasks: CalendarTask[] = $state([]);
  let status: CalendarStatus | null = $state(null);
  let loading = $state(true);
  let syncing = $state(false);

  let viewYear = $state(new Date().getFullYear());
  let viewMonth = $state(new Date().getMonth()); // 0-based
  let selectedDay = $state<string | null>(null);

  // Quick-add state
  let quickAddTitle = $state('');
  let quickAddTime = $state('');
  let quickAddPriority = $state<CalendarTaskPriority>('MEDIUM');
  let publishToGoogle = $state(false);
  let addingTask = $state(false);

  // Inline edit state
  let editingTaskId = $state<number | null>(null);
  let editTitle = $state('');
  let editTime = $state('');
  let editEndTime = $state('');

  const dtFormatter = new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  });

  function eventDay(event: CalendarEvent): string {
    const d = new Date(event.start_at);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  function taskDay(task: CalendarTask): string {
    return task.date;
  }

  const todayKey = `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}-${String(new Date().getDate()).padStart(2, '0')}`;

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
    for (const [key, evts] of monthEvents) {
      byDay.set(
        key,
        evts.map((ev) => ({
          kind: 'google' as const,
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

  function prevMonth(): void {
    if (viewMonth === 0) {
      viewYear -= 1;
      viewMonth = 11;
    } else {
      viewMonth -= 1;
    }
  }

  function nextMonth(): void {
    if (viewMonth === 11) {
      viewYear += 1;
      viewMonth = 0;
    } else {
      viewMonth += 1;
    }
  }

  function goToday(): void {
    viewYear = new Date().getFullYear();
    viewMonth = new Date().getMonth();
    selectedDay = todayKey;
  }

  function eventTime(ev: CalendarEvent): string {
    if (ev.all_day) return $t('calendar.allDay');
    return dtFormatter.format(new Date(ev.start_at));
  }

  async function refresh(): Promise<void> {
    try {
      const [evts, st, tks] = await Promise.all([
        api.google.calendarEvents(),
        api.google.calendarStatus(),
        api.calendarTasks.list(),
      ]);
      events = evts;
      status = st;
      tasks = tks;
    } catch (e) {
      logger.error(e);
    } finally {
      loading = false;
    }
  }

  async function sync(): Promise<void> {
    syncing = true;
    try {
      await api.google.calendarSync();
      showNotification($t('calendar.syncOk'), 'success');
      await refresh();
    } catch (e) {
      logger.error(e);
    } finally {
      syncing = false;
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
      });
      if (publishToGoogle && status?.connected) {
        try {
          const start = quickAddTime
            ? `${selectedDay}T${quickAddTime}:00`
            : selectedDay;
          const end = quickAddTime
            ? `${selectedDay}T${addHour(quickAddTime)}:00`
            : selectedDay;
          const created = await api.google.calendarCreateEvent({
            summary: title,
            start: quickAddTime ? { dateTime: start } : { date: start },
            end: quickAddTime ? { dateTime: end } : { date: end },
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
    } catch (e) {
      logger.error(e);
      showNotification($t('calendar.taskAddError'), 'error');
    } finally {
      addingTask = false;
    }
  }

  function addHour(hhmm: string): string {
    const [h, m] = hhmm.split(':').map(Number);
    const nh = (h + 1) % 24;
    return `${String(nh).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
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
  }

  async function saveEdit(task: CalendarTask): Promise<void> {
    const title = editTitle.trim();
    if (!title) return;
    await updateTask(task, {
      title,
      start_time: editTime ? `${editTime}:00` : null,
      end_time: editEndTime ? `${editEndTime}:00` : null,
    });
    if (task.google_event_id && status?.connected) {
      try {
        const day = task.date;
        const start = editTime ? `${day}T${editTime}:00` : day;
        const end = editEndTime
          ? `${day}T${editEndTime}:00`
          : editTime
            ? `${day}T${addHour(editTime)}:00`
            : day;
        await api.google.calendarUpdateEvent(task.google_event_id, {
          summary: title,
          start: editTime ? { dateTime: start } : { date: start },
          end: editTime ? { dateTime: end } : { date: end },
        });
        await refresh();
      } catch (e) {
        logger.warn('Google update failed', e);
        showNotification($t('calendar.googlePublishError'), 'error');
      }
    }
    editingTaskId = null;
  }

  function priorityClass(priority: CalendarTaskPriority): string {
    return `prio prio-${priority.toLowerCase()}`;
  }

  function openSettings(): void {
    window.dispatchEvent(new CustomEvent('joidy:open-settings'));
  }

  onMount(async () => {
    await refresh();
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
      <button class="btn btn-ghost" onclick={sync} disabled={syncing || !status?.connected}>
        <span class={syncing ? 'spin' : ''}><RefreshCw size={13} /></span>
        {syncing ? $t('calendar.syncing') : $t('calendar.sync')}
      </button>
    </div>
  </div>

  {#if loading}
    <div class="loading-state caption">{$t('calendar.loading')}</div>
  {:else if status && !status.connected}
    <div class="empty-wrap">
      <EmptyState title={$t('calendar.notConnected')} message={$t('calendar.notConnectedHint')} actionLabel={$t('calendar.goToSettings')} onAction={openSettings}>
        {#snippet icon()}<Settings size={44} />{/snippet}
      </EmptyState>
    </div>
  {:else}
    <div class="calendar-body">
      <div class="calendar-card">
        <div class="calendar-toolbar">
          <button class="btn btn-ghost nav-btn" onclick={prevMonth} aria-label={$t('calendar.prevMonth')}>
            <ChevronLeft size={16} />
          </button>
          <span class="month-label">
            {$t(`calendar.months.${viewMonth}`)} {viewYear}
          </span>
          <button class="btn btn-ghost nav-btn" onclick={goToday}>{$t('calendar.today')}</button>
          <button class="btn btn-ghost nav-btn" onclick={nextMonth} aria-label={$t('calendar.nextMonth')}>
            <ChevronRight size={16} />
          </button>
        </div>

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
              onclick={() => (selectedDay = selectedDay === cell.key ? null : cell.key)}
            >
              <span class="day-num">{cell.day}</span>
              <span class="cell-items">
                {#each items.slice(0, 2) as item}
                  {#if item.kind === 'google'}
                    <span class="chip chip-google"><Lock size={8} />{item.label}</span>
                  {:else}
                    <span class="chip {priorityClass(item.task.priority)}" class:done={item.task.done}>{item.label}</span>
                  {/if}
                {/each}
                {#if items.length > 2}
                  <span class="chip chip-more">+{items.length - 2}</span>
                {/if}
              </span>
            </button>
          {/each}
        </div>
      </div>

      <div class="day-detail">
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
              {#each selectedDayItems as item (item.kind === 'google' ? `g-${item.label}-${item.time}` : `t-${item.task.id}`)}
                {#if item.kind === 'google'}
                  <div class="event-item">
                    <span class="event-time caption">{item.allDay ? $t('calendar.allDay') : item.time}</span>
                    <span class="event-summary"><Lock size={10} class="lock-icon" /> {item.label}</span>
                    {#if item.location}
                      <span class="event-location caption">{item.location}</span>
                    {/if}
                  </div>
                {:else}
                  <div class="event-item task-item" class:done={item.task.done}>
                    {#if editingTaskId === item.task.id}
                      <div class="edit-form">
                        <input class="edit-input" type="text" bind:value={editTitle} maxlength="500" />
                        <div class="edit-times">
                          <input class="edit-input" type="time" bind:value={editTime} />
                          <input class="edit-input" type="time" bind:value={editEndTime} />
                        </div>
                        <div class="edit-actions">
                          <button class="btn btn-ghost icon-btn" onclick={() => saveEdit(item.task)} aria-label={$t('calendar.save')}>
                            <Check size={13} />
                          </button>
                          <button class="btn btn-ghost icon-btn" onclick={() => (editingTaskId = null)} aria-label={$t('calendar.cancel')}>
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
                      <button class="prio-btn {priorityClass(item.task.priority)}" onclick={() => cyclePriority(item.task)} title={$t('calendar.priority')} aria-label={$t('calendar.priority')}>
                        {item.task.priority.slice(0, 1)}
                      </button>
                      <span class="event-summary">{item.task.title}</span>
                      <span class="task-actions">
                        <button class="btn btn-ghost icon-btn" onclick={() => startEdit(item.task)} aria-label={$t('calendar.edit')}>
                          <Pencil size={12} />
                        </button>
                        <button class="btn btn-ghost icon-btn" onclick={() => removeTask(item.task)} aria-label={$t('calendar.delete')}>
                          <Trash2 size={12} />
                        </button>
                      </span>
                    {/if}
                  </div>
                {/if}
              {/each}
            </div>
          {/if}

          <form class="quick-add" onsubmit={(e) => { e.preventDefault(); addTask(); }}>
            <input
              class="quick-input"
              type="text"
              bind:value={quickAddTitle}
              placeholder={$t('calendar.quickAddPlaceholder')}
              maxlength="500"
              disabled={addingTask}
            />
            <input class="quick-time" type="time" bind:value={quickAddTime} disabled={addingTask} />
            <select class="quick-prio" bind:value={quickAddPriority} disabled={addingTask} aria-label={$t('calendar.priority')}>
              {#each PRIORITIES as p}
                <option value={p}>{p}</option>
              {/each}
            </select>
            {#if status?.connected}
              <label class="publish-toggle" title={$t('calendar.publishToGoogleHint')}>
                <input type="checkbox" bind:checked={publishToGoogle} disabled={addingTask} />
                <span class="publish-label"><Lock size={10} />{$t('calendar.publishToGoogle')}</span>
              </label>
            {/if}
            <button type="submit" class="btn btn-ghost icon-btn" disabled={addingTask || !quickAddTitle.trim()} aria-label={$t('calendar.addTask')}>
              <Plus size={14} />
            </button>
          </form>
        {:else}
          <h4>{$t('calendar.pickDay')}</h4>
          <span class="caption">{$t('calendar.pickDayHint')}</span>
        {/if}
      </div>
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

  .chip-more {
    color: var(--text-muted);
    background: transparent;
  }

  .prio-low { color: var(--text-muted); }
  .prio-medium { color: var(--accent); }
  .prio-high { color: #e08c3a; }
  .prio-urgent { color: #d9534f; }

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
  }

  .quick-time,
  .quick-prio {
    width: auto;
    flex-shrink: 0;
  }

  .quick-prio {
    max-width: 80px;
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
  }

  .publish-toggle input {
    display: none;
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

  .empty-wrap {
    padding: var(--s4) 0;
  }

  .spin {
    animation: spin 1s linear infinite;
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
