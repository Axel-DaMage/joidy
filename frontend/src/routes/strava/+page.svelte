<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { SvelteSet } from 'svelte/reactivity';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import { Activity, RefreshCw, TriangleAlert, Unlink, UserRound } from 'lucide-svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ModalDialog from '$lib/components/ModalDialog.svelte';
  import StravaActivityCard from '$lib/components/strava/StravaActivityCard.svelte';
  import StravaActivityDetail from '$lib/components/strava/StravaActivityDetail.svelte';
  import StravaStatsPanel from '$lib/components/strava/StravaStatsPanel.svelte';
  import StravaRoutesList from '$lib/components/strava/StravaRoutesList.svelte';
  import { api } from '$lib/api';
  import { showNotification } from '$lib/stores/notifications';
  import { locale } from '$lib/stores/locale';
  import { logger } from '$lib/utils/logger';
  import {
    formatNumber,
    sportCategory,
    sportCategoryKey,
    sportIconName,
  } from '$lib/strava/format';
  import { isStravaAuthError, stravaErrorKind } from '$lib/strava/errors';
  import { t } from 'svelte-i18n';
  import type {
    StravaActivity,
    StravaAthleteSummary,
    StravaRoute,
    StravaStats,
    StravaStatus,
  } from '$lib/strava/types';

  // How many activity cards render before "show more" expands the list.
  const PAGE_SIZE = 12;
  // Fetched window: covers a month of daily activities for the weekly/monthly
  // summaries while staying a single upstream request.
  const FETCH_PER_PAGE = 60;

  type Tab = 'activities' | 'routes';

  let status = $state<StravaStatus | null>(null);
  let athlete = $state<StravaAthleteSummary | null>(null);
  let activities = $state<StravaActivity[]>([]);
  let stats = $state<StravaStats | null>(null);
  let routes = $state<StravaRoute[]>([]);

  let bootLoading = $state(true);
  let dashboardLoading = $state(false);
  let activitiesError = $state('');
  let routesLoading = $state(false);
  let routesLoaded = $state(false);
  let routesError = $state('');
  let syncing = $state(false);

  let tab = $state<Tab>('activities');
  let sportFilter = $state<string>('all'); // 'all' | SportCategory
  let visibleCount = $state(PAGE_SIZE);
  let selectedActivityId = $state<number | null>(null);

  let connecting = $state(false);
  let connectError = $state('');
  let pollInterval: ReturnType<typeof setInterval> | null = null;
  let pollTimeout: ReturnType<typeof setTimeout> | null = null;
  let destroyed = false;

  const connected = $derived(status?.connected ?? false);
  const configured = $derived(status?.configured ?? false);

  const athleteName = $derived.by(() => {
    if (!athlete) return '';
    const full = [athlete.firstname, athlete.lastname].filter(Boolean).join(' ').trim();
    return full || athlete.username || '';
  });
  const athleteLocation = $derived.by(() => {
    if (!athlete) return '';
    return [athlete.city, athlete.state, athlete.country].filter(Boolean).join(', ');
  });

  // Sport filter chips: only categories actually present in the window.
  const availableCategories = $derived.by(() => {
    const set = new SvelteSet<string>();
    for (const a of activities) set.add(sportCategory(a.sport_type, a.type));
    return [...set];
  });

  const filteredActivities = $derived.by(() => {
    if (sportFilter === 'all') return activities;
    return activities.filter(
      (a) => sportCategory(a.sport_type, a.type) === sportFilter
    );
  });

  const visibleActivities = $derived(filteredActivities.slice(0, visibleCount));
  const hasMore = $derived(visibleCount < filteredActivities.length);

  onMount(async () => {
    await loadStatus();
    if (connected) await loadDashboard();
  });

  onDestroy(() => {
    destroyed = true;
    stopPolling();
  });

  async function loadStatus(): Promise<void> {
    try {
      status = await api.strava.status();
      athlete = status.athlete;
    } catch (e) {
      logger.warn('strava status failed', e);
      status = { configured: false, connected: false, athlete: null };
    } finally {
      bootLoading = false;
    }
  }

  async function loadDashboard(): Promise<void> {
    dashboardLoading = true;
    activitiesError = '';
    // Partial-failure tolerant: stats/routes degrade independently.
    const [athleteRes, statsRes, activitiesRes] = await Promise.allSettled([
      api.strava.athlete(),
      api.strava.stats(),
      api.strava.activities({ per_page: FETCH_PER_PAGE, page: 1 }),
    ]);
    if (athleteRes.status === 'fulfilled') athlete = athleteRes.value;
    if (statsRes.status === 'fulfilled') stats = statsRes.value;
    if (activitiesRes.status === 'fulfilled') {
      activities = activitiesRes.value;
    } else {
      activitiesError = stravaErrorMessage(activitiesRes.reason);
      if (isStravaAuthError(activitiesRes.reason)) {
        // Provider token died between /status and the data call — flip the
        // page back to the connect state instead of an error list.
        status = { ...(status ?? { configured: true, connected: false, athlete: null }), connected: false };
      }
    }
    dashboardLoading = false;
  }

  async function loadRoutes(): Promise<void> {
    if (routesLoaded || routesLoading) return;
    routesLoading = true;
    routesError = '';
    try {
      routes = await api.strava.routes({ per_page: 50, page: 1 });
      routesLoaded = true;
    } catch (e) {
      routesError = stravaErrorMessage(e);
    } finally {
      routesLoading = false;
    }
  }

  function setTab(next: Tab): void {
    tab = next;
    if (next === 'routes') void loadRoutes();
  }

  function setSportFilter(cat: string): void {
    sportFilter = cat;
    visibleCount = PAGE_SIZE;
  }

  function showMore(): void {
    visibleCount += PAGE_SIZE;
  }

  function openActivity(id: number): void {
    selectedActivityId = id;
  }

  function closeActivity(): void {
    selectedActivityId = null;
  }

  // ── OAuth connect (popup + status poll, mirrors SettingsGoogle) ──────────

  function stopPolling(): void {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    if (pollTimeout) {
      clearTimeout(pollTimeout);
      pollTimeout = null;
    }
  }

  async function startConnect(): Promise<void> {
    connecting = true;
    connectError = '';
    try {
      const data = await api.strava.authUrl();
      window.open(data.url, '_blank', 'noopener,noreferrer');
      pollInterval = setInterval(async () => {
        await loadStatus();
        if (destroyed || pollInterval === null) return;
        if (connected) {
          stopPolling();
          connecting = false;
          showNotification($t('strava.connect.connectedToast'), 'success');
          await loadDashboard();
        }
      }, 3000);
      pollTimeout = setTimeout(() => {
        stopPolling();
        connecting = false;
        if (!connected && !destroyed) {
          connectError = $t('strava.connect.timeout');
        }
      }, 300000);
    } catch (e) {
      connectError = stravaErrorMessage(e);
      connecting = false;
    }
  }

  async function disconnect(): Promise<void> {
    try {
      await api.strava.disconnect();
      status = { configured: status?.configured ?? false, connected: false, athlete: null };
      athlete = null;
      activities = [];
      stats = null;
      routes = [];
      routesLoaded = false;
      showNotification($t('strava.connect.disconnectedToast'), 'info');
    } catch (e) {
      showNotification(stravaErrorMessage(e), 'error');
    }
  }

  // ── Sync + gamification ────────────────────────────────────────────────────

  async function runSync(): Promise<void> {
    if (syncing) return;
    syncing = true;
    try {
      const result = await api.strava.sync();
      if (result.xp_awarded > 0) {
        showNotification(
          $t('strava.sync.result', {
            values: { xp: result.xp_awarded, count: result.new },
          }),
          'level'
        );
      } else {
        showNotification(
          $t('strava.sync.upToDate', { values: { count: result.fetched } }),
          'info'
        );
      }
      // Refresh the window so newly synced activities appear immediately.
      await loadDashboard();
    } catch (e) {
      showNotification(stravaErrorMessage(e), 'error');
    } finally {
      syncing = false;
    }
  }

  // ── Error mapping (backend contract: 401→reconnect, 429→rate-limit, …) ────

  function stravaErrorMessage(e: unknown): string {
    return $t(`strava.errors.${stravaErrorKind(e)}`);
  }
</script>

<div class="strava-page">
  <div class="strava-header">
    <div>
      <h3>{$t('strava.title')}</h3>
      <span class="caption">{$t('strava.subtitle')}</span>
    </div>
    {#if connected}
      <div class="header-actions">
        <button class="action-btn" class:syncing onclick={runSync} disabled={syncing}>
          <RefreshCw size={13} />
          {syncing ? $t('strava.sync.syncing') : $t('strava.sync.button')}
        </button>
        <button class="action-btn ghost" onclick={disconnect}>
          {$t('strava.connect.disconnect')}
        </button>
      </div>
    {/if}
  </div>

  {#if bootLoading}
    <div class="state caption">{$t('strava.loading')}</div>
  {:else if !configured}
    <div class="state-wrap">
      <EmptyState title={$t('strava.notConfigured.title')} message={$t('strava.notConfigured.hint')}>
        {#snippet icon()}<Unlink size={44} />{/snippet}
      </EmptyState>
    </div>
  {:else if !connected}
    <div class="state-wrap">
      <EmptyState
        title={$t('strava.connect.title')}
        message={connecting ? $t('strava.connect.waiting') : $t('strava.connect.hint')}
        actionLabel={connecting ? '' : $t('strava.connect.button')}
        onAction={connecting ? null : startConnect}
      >
        {#snippet icon()}<Activity size={44} />{/snippet}
      </EmptyState>
      {#if connectError}
        <p class="connect-error">{connectError}</p>
      {/if}
    </div>
  {:else}
    <!-- Athlete header -->
    <div class="athlete-card">
      <div class="athlete-avatar">
        {#if athlete?.profile}
          <img src={athlete.profile} alt={athleteName} loading="lazy" />
        {:else}
          <UserRound size={26} />
        {/if}
      </div>
      <div class="athlete-info">
        <div class="athlete-name">{athleteName || $t('strava.athlete.fallback')}</div>
        <div class="athlete-sub caption">
          {#if athlete?.username}@{athlete.username}{/if}
          {#if athleteLocation} · {athleteLocation}{/if}
        </div>
      </div>
      <div class="athlete-badge caption">
        <Activity size={12} />
        {$t('strava.connectedBadge')}
      </div>
    </div>

    <!-- Stats summary (week / month / YTD / all-time) -->
    <StravaStatsPanel {stats} {activities} loading={dashboardLoading && activities.length === 0} />

    <!-- Tabs -->
    <div class="tab-bar" role="tablist">
      <button
        class="tab-btn"
        class:active={tab === 'activities'}
        role="tab"
        aria-selected={tab === 'activities'}
        onclick={() => setTab('activities')}
      >
        {$t('strava.tabs.activities')}
      </button>
      <button
        class="tab-btn"
        class:active={tab === 'routes'}
        role="tab"
        aria-selected={tab === 'routes'}
        onclick={() => setTab('routes')}
      >
        {$t('strava.tabs.routes')}
      </button>
    </div>

    {#if tab === 'activities'}
      {#if availableCategories.length > 1}
        <div class="sport-chips">
          <button
            class="chip"
            class:active={sportFilter === 'all'}
            onclick={() => setSportFilter('all')}
          >
            {$t('strava.filters.all')}
          </button>
          {#each availableCategories as cat (cat)}
            <button
              class="chip"
              class:active={sportFilter === cat}
              onclick={() => setSportFilter(cat)}
            >
              <DynamicIcon name={sportIconName(cat)} size={12} />
              {$t(`strava.${sportCategoryKey(cat)}`)}
            </button>
          {/each}
        </div>
      {/if}

      {#if dashboardLoading && activities.length === 0}
        <div class="state caption">{$t('strava.activities.loading')}</div>
      {:else if activitiesError}
        <div class="state-wrap">
          <EmptyState title={$t('strava.activities.loadFailed')} message={activitiesError}>
            {#snippet icon()}<TriangleAlert size={44} />{/snippet}
            <button
              class="action-btn"
              onclick={() => {
                void loadDashboard();
              }}
              >{$t('common.retry')}</button
            >
          </EmptyState>
        </div>
      {:else if filteredActivities.length === 0}
        <div class="state-wrap">
          <EmptyState
            title={sportFilter === 'all' ? $t('strava.activities.empty') : $t('strava.activities.emptyFilter')}
            message={$t('strava.activities.syncHint')}
          >
            {#snippet icon()}<Activity size={44} />{/snippet}
          </EmptyState>
        </div>
      {:else}
        <div class="activities-list">
          {#each visibleActivities as activity (activity.id)}
            <StravaActivityCard {activity} onselect={openActivity} />
          {/each}
        </div>
        {#if hasMore}
          <button class="action-btn load-more" onclick={showMore}>
            {$t('strava.activities.showMore', {
              values: { count: filteredActivities.length - visibleCount },
            })}
          </button>
        {/if}
        <div class="caption list-foot">
          {formatNumber(activities.length, $locale)} {$t('strava.activities.fetchedNote')}
        </div>
      {/if}
    {:else}
      <StravaRoutesList
        {routes}
        loading={routesLoading}
        loadError={routesError}
        onretry={loadRoutes}
      />
    {/if}
  {/if}
</div>

<!-- Activity detail modal -->
{#if selectedActivityId !== null}
  <ModalDialog
    open={true}
    title={$t('strava.detail.title')}
    size="lg"
    onClose={closeActivity}
  >
    <StravaActivityDetail activityId={selectedActivityId} />
  </ModalDialog>
{/if}

<style>
  .strava-page {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 860px;
    margin: 0 auto;
    padding: 16px 8px 32px;
  }

  .strava-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  h3 {
    margin: 0;
    color: var(--text-primary);
  }

  .header-actions {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }

  .action-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--accent);
    color: #fff;
    font-size: 12px;
    font-family: var(--font-mono);
    cursor: pointer;
  }

  .action-btn:hover:not(:disabled) {
    opacity: 0.9;
  }

  .action-btn:disabled {
    opacity: 0.6;
    cursor: default;
  }

  .action-btn.ghost {
    background: transparent;
    color: var(--text-secondary);
  }

  .action-btn.ghost:hover {
    border-color: var(--text-muted);
    color: var(--text-primary);
  }

  .action-btn.syncing :global(svg) {
    animation: strava-spin 1s linear infinite;
  }

  @keyframes strava-spin {
    to {
      transform: rotate(360deg);
    }
  }

  .state {
    text-align: center;
    padding: 32px 0;
    color: var(--text-muted);
  }

  .state-wrap {
    padding: 16px 0;
  }

  .connect-error {
    text-align: center;
    color: var(--danger);
    font-size: 12px;
    margin: 8px 0 0;
  }

  .athlete-card {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px 16px;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: var(--surface);
  }

  .athlete-avatar {
    flex-shrink: 0;
    width: 52px;
    height: 52px;
    border-radius: 50%;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    background: color-mix(in srgb, var(--accent) 14%, transparent);
    color: var(--accent);
  }

  .athlete-avatar img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .athlete-info {
    flex: 1;
    min-width: 0;
  }

  .athlete-name {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .athlete-sub {
    color: var(--text-muted);
    margin-top: 2px;
  }

  .athlete-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    color: var(--success);
    border: 1px solid color-mix(in srgb, var(--success) 40%, transparent);
    border-radius: 999px;
    padding: 4px 10px;
    flex-shrink: 0;
  }

  .tab-bar {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid var(--border);
  }

  .tab-btn {
    padding: 8px 14px;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-muted);
    font-size: 12px;
    font-family: var(--font-mono);
    cursor: pointer;
  }

  .tab-btn:hover {
    color: var(--text-primary);
  }

  .tab-btn.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }

  .sport-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 11px;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: transparent;
    color: var(--text-secondary);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .chip:hover {
    border-color: var(--accent);
    color: var(--text-primary);
  }

  .chip.active {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
  }

  .activities-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .load-more {
    align-self: center;
    margin-top: 4px;
  }

  .list-foot {
    text-align: center;
    color: var(--text-muted);
  }
</style>
