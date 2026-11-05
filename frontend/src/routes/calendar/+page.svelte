<script lang="ts">
  import { onMount } from 'svelte';
  import { api, type CalendarEvent } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import { showNotification } from '$lib/stores/notifications';
  import { ChevronLeft, ChevronRight, CalendarDays, RefreshCw, Settings } from 'lucide-svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { t } from 'svelte-i18n';

  interface CalendarStatus {
    connected: boolean;
    calendars: number;
    cached_events: number;
    last_synced_at: string | null;
  }

  let events: CalendarEvent[] = $state([]);
  let status: CalendarStatus | null = $state(null);
  let loading = $state(true);
  let syncing = $state(false);

  let viewYear = $state(new Date().getFullYear());
  let viewMonth = $state(new Date().getMonth()); // 0-based
  let selectedDay = $state<string | null>(null);

  const dtFormatter = new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  });

  function eventDay(event: CalendarEvent): string {
    const d = new Date(event.start_at);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
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

  let selectedDayEvents = $derived(selectedDay ? (monthEvents.get(selectedDay) ?? []) : []);

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
    selectedDay = null;
  }

  function eventTime(ev: CalendarEvent): string {
    if (ev.all_day) return $t('calendar.allDay');
    return dtFormatter.format(new Date(ev.start_at));
  }

  async function refresh(): Promise<void> {
    try {
      const [evts, st] = await Promise.all([
        api.google.calendarEvents(),
        api.google.calendarStatus(),
      ]);
      events = evts;
      status = st;
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
          <button
            class="day-cell"
            class:out={!cell.inMonth}
            class:today={cell.key === todayKey}
            class:selected={selectedDay === cell.key}
            class:has-events={(monthEvents.get(cell.key) ?? []).length > 0}
            onclick={() => (selectedDay = selectedDay === cell.key ? null : cell.key)}
          >
            <span class="day-num">{cell.day}</span>
            {#if (monthEvents.get(cell.key) ?? []).length > 0}
              <span class="event-dot"></span>
            {/if}
          </button>
        {/each}
      </div>
    </div>

    {#if selectedDay}
      <div class="day-detail">
        <h4>
          {new Date(`${selectedDay}T12:00:00`).toLocaleDateString(undefined, {
            weekday: 'long',
            day: 'numeric',
            month: 'long',
          })}
        </h4>
        {#if selectedDayEvents.length === 0}
          <span class="caption">{$t('calendar.noEventsDay')}</span>
        {:else}
          <div class="event-list">
            {#each selectedDayEvents as ev (ev.google_id)}
              <div class="event-item">
                <span class="event-time caption">{eventTime(ev)}</span>
                <span class="event-summary">{ev.summary || '—'}</span>
                {#if ev.location}
                  <span class="event-location caption">{ev.location}</span>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {:else if events.length === 0}
      <div class="empty-wrap">
        <EmptyState title={$t('calendar.empty')} message={$t('calendar.emptyHint')}>
          {#snippet icon()}<CalendarDays size={44} />{/snippet}
        </EmptyState>
      </div>
    {/if}
  {/if}
</div>

<style>
  .calendar-page {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 860px;
    margin: 0 auto;
    padding: var(--s4) var(--s3);
    width: 100%;
  }

  .calendar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .calendar-header h3 {
    margin: 0;
  }

  .calendar-actions {
    display: flex;
    gap: 8px;
  }

  .calendar-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3);
  }

  .calendar-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: var(--s2);
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
  }

  .weekday {
    text-align: center;
    font-size: 11px;
  }

  .day-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 4px;
  }

  .day-cell {
    position: relative;
    aspect-ratio: 1 / 0.85;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    border: 1px solid transparent;
    border-radius: calc(var(--r) * 0.6);
    background: transparent;
    cursor: pointer;
    color: var(--text-primary);
    font-size: 12px;
  }

  .day-cell:hover {
    background: var(--hover);
  }

  .day-cell.out {
    color: var(--text-muted);
    opacity: 0.5;
  }

  .day-cell.today {
    border-color: var(--accent);
  }

  .day-cell.selected {
    background: var(--accent);
    color: #fff;
  }

  .event-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--accent);
  }

  .day-cell.selected .event-dot {
    background: #fff;
  }

  .day-detail {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3);
  }

  .day-detail h4 {
    margin: 0 0 var(--s2);
    text-transform: capitalize;
  }

  .event-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .event-item {
    display: flex;
    align-items: baseline;
    gap: 10px;
    padding: 6px 8px;
    border: 1px solid var(--border);
    border-radius: calc(var(--r) * 0.6);
  }

  .event-time {
    min-width: 64px;
  }

  .event-summary {
    font-weight: 500;
  }

  .event-location {
    margin-left: auto;
    text-align: right;
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
    .event-location {
      display: none;
    }
  }
</style>
