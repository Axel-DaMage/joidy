<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api, type CalendarEvent, type GoogleCalendarListItem } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import { loadUserSettings, patchUserSettings } from '$lib/utils/userSettings';
  import { use24HourClock } from '$lib/stores/settings';
  import { locale as localeStore } from '$lib/stores/locale';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import CalendarDays from 'lucide-svelte/icons/calendar-days';
  import Settings from 'lucide-svelte/icons/settings';
  import { t } from 'svelte-i18n';

  /**
   * "Calendario sagrado" — read-only side panel for the execution view (#1201).
   * Shows today's Google Calendar events so the user can work the queue around
   * immovable commitments. No create/edit — the chosen calendar_id persists in
   * userSettings.executionUi.
   */

  interface GoogleStatus {
    connected: boolean;
    calendars: number;
    cached_events: number;
    last_synced_at: string | null;
  }

  let status = $state<GoogleStatus | null>(null);
  let calendars = $state<GoogleCalendarListItem[]>([]);
  let events = $state<CalendarEvent[]>([]);
  let loading = $state(true);
  let selectedCalendarId = $state<string | null>(
    loadUserSettings().executionUi?.calendarId ?? null
  );
  // Ticker so the "in progress" highlight and "now" marker stay honest.
  let now = $state(new Date());
  let nowTimer: ReturnType<typeof setInterval> | null = null;

  let todayEvents = $derived.by(() => {
    const dayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const dayEnd = new Date(dayStart);
    dayEnd.setDate(dayEnd.getDate() + 1);
    return events
      .filter((ev) => {
        const start = new Date(ev.start_at);
        return start >= dayStart && start < dayEnd;
      })
      .sort((a, b) => a.start_at.localeCompare(b.start_at));
  });

  let timeFormatter = $derived(
    new Intl.DateTimeFormat($localeStore, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: !$use24HourClock,
    })
  );

  function isInProgress(ev: CalendarEvent): boolean {
    if (ev.all_day) return true;
    const start = new Date(ev.start_at).getTime();
    const end = ev.end_at ? new Date(ev.end_at).getTime() : start;
    const ts = now.getTime();
    return start <= ts && ts <= end;
  }

  function eventTimeLabel(ev: CalendarEvent): string {
    if (ev.all_day) return $t('executionPage.allDay');
    return timeFormatter.format(new Date(ev.start_at));
  }

  function calendarLabel(cal: GoogleCalendarListItem): string {
    return cal.summary?.trim() || cal.id;
  }

  function openSettings(): void {
    window.dispatchEvent(new CustomEvent('joidy:open-settings'));
  }

  function onCalendarChange(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    selectedCalendarId = value === '' ? null : value;
    patchUserSettings({ executionUi: { calendarId: selectedCalendarId } });
    void loadEvents();
  }

  // Auto-sync staleness threshold — same rule as /calendar's maybeAutoSync:
  // pull from Google when the cache is older than this (or never synced).
  const AUTO_SYNC_STALE_MS = 15 * 60 * 1000;

  async function loadEvents(): Promise<void> {
    const dayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const dayEnd = new Date(dayStart);
    dayEnd.setDate(dayEnd.getDate() + 1);
    try {
      events = await api.google.calendarEvents({
        start: dayStart.toISOString(),
        end: dayEnd.toISOString(),
        calendar_id: selectedCalendarId ?? undefined,
      });
    } catch (e) {
      logger.error('[SacredCalendar] events fetch failed:', e);
      events = [];
    }
  }

  async function maybeAutoSync(): Promise<void> {
    if (!status?.connected) return;
    const last = status.last_synced_at ? new Date(status.last_synced_at).getTime() : 0;
    if (Date.now() - last <= AUTO_SYNC_STALE_MS) return;
    try {
      await api.google.calendarSync();
      await loadEvents();
    } catch (e) {
      logger.warn('[SacredCalendar] auto-sync failed:', e);
    }
  }

  onMount(async () => {
    // intentional: module-store-free interval owned by the component;
    // cleared in onDestroy.
    nowTimer = setInterval(() => {
      now = new Date();
    }, 30_000);
    try {
      status = await api.google.calendarStatus();
      if (status.connected) {
        const [cals] = await Promise.all([
          api.google.calendars().catch((e) => {
            logger.warn('[SacredCalendar] calendar list failed:', e);
            return [] as GoogleCalendarListItem[];
          }),
          loadEvents(),
        ]);
        calendars = cals;
        // Drop a stale persisted selection that no longer exists.
        if (selectedCalendarId !== null && !calendars.some((c) => c.id === selectedCalendarId)) {
          selectedCalendarId = null;
          patchUserSettings({ executionUi: { calendarId: null } });
          await loadEvents();
        }
        await maybeAutoSync();
      }
    } catch (e) {
      logger.error('[SacredCalendar] status fetch failed:', e);
      status = null;
    } finally {
      loading = false;
    }
  });

  onDestroy(() => {
    if (nowTimer) clearInterval(nowTimer);
  });
</script>

<aside class="sacred-calendar card">
  <div class="sacred-header">
    <div class="sacred-title-row">
      <CalendarDays size={15} />
      <h4>{$t('executionPage.sacredTitle')}</h4>
    </div>
    <span class="sacred-sub caption">{$t('executionPage.sacredHint')}</span>
  </div>

  {#if loading}
    <div class="sacred-body caption">{$t('executionPage.loading')}</div>
  {:else if !status?.connected}
    <EmptyState
      title={$t('executionPage.notConnected')}
      message={$t('executionPage.notConnectedHint')}
      actionLabel={$t('executionPage.goToSettings')}
      onAction={openSettings}
    >
      {#snippet icon()}<Settings size={40} />{/snippet}
    </EmptyState>
  {:else}
    {#if calendars.length > 1}
      <select
        class="input calendar-picker"
        value={selectedCalendarId ?? ''}
        onchange={onCalendarChange}
        aria-label={$t('executionPage.allCalendars')}
      >
        <option value="">{$t('executionPage.allCalendars')}</option>
        {#each calendars as cal (cal.id)}
          <option value={cal.id}>{calendarLabel(cal)}</option>
        {/each}
      </select>
    {/if}

    {#if todayEvents.length === 0}
      <div class="sacred-body caption">{$t('executionPage.noEvents')}</div>
    {:else}
      <ul class="sacred-list">
        {#each todayEvents as ev (ev.google_id)}
          {@const live = isInProgress(ev)}
          <li class="sacred-event" class:live>
            <span class="sacred-time mono">{eventTimeLabel(ev)}</span>
            <span class="sacred-name" title={ev.summary ?? ''}>
              {ev.summary?.trim() || '—'}
            </span>
            {#if live}
              <span class="live-dot" title={$t('executionPage.now')}></span>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</aside>

<style>
  .sacred-calendar {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    padding: var(--s4);
    min-width: 0;
  }

  .sacred-header {
    display: flex;
    flex-direction: column;
    gap: var(--s1);
    padding-bottom: var(--s2);
    border-bottom: 1px solid var(--border);
  }

  .sacred-title-row {
    display: flex;
    align-items: center;
    gap: var(--s2);
    color: var(--text-primary);
  }

  .sacred-title-row h4 {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.04em;
  }

  .sacred-sub {
    font-size: 11px;
    color: var(--text-muted);
  }

  .caption {
    font-size: 12px;
    color: var(--text-muted);
  }

  .sacred-body {
    padding: var(--s4) 0;
    text-align: center;
  }

  .calendar-picker {
    font-size: 12px;
    padding: var(--s1_5) var(--s2);
    width: 100%;
  }

  .sacred-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s1);
    overflow-y: auto;
    max-height: 420px;
  }

  .sacred-event {
    display: flex;
    align-items: center;
    gap: var(--s2);
    padding: var(--s1_5) var(--s2);
    border-radius: var(--r-sm, 4px);
    font-size: 12px;
    color: var(--text-secondary);
    border: 1px solid transparent;
    min-width: 0;
  }

  .sacred-event.live {
    color: var(--text-primary);
    border-color: color-mix(in srgb, var(--xp) 40%, var(--border));
    background: color-mix(in srgb, var(--xp) 8%, transparent);
  }

  .sacred-time {
    font-size: 11px;
    color: var(--text-muted);
    flex-shrink: 0;
    min-width: 48px;
  }

  .sacred-event.live .sacred-time {
    color: var(--xp);
  }

  .sacred-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .live-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--xp);
    flex-shrink: 0;
    animation: sacred-pulse 2s ease-in-out infinite;
  }

  @keyframes sacred-pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.35;
    }
  }
</style>
