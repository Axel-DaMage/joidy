<script lang="ts">
  import { onMount } from 'svelte';
  import { t } from 'svelte-i18n';
  import { api, type AnalyticsDashboard } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import { trackFeatureUse } from '$lib/stores/usage';

  let dashboard: AnalyticsDashboard | null = null;
  let loading = true;
  let error = '';
  let days = 30;

  // Derived chart data — kept as plain let + reactive statements for clarity.
  $: activityDays = dashboard?.activity.days ?? [];
  $: maxNotes = Math.max(1, ...activityDays.map((d) => d.notes_created));
  $: maxXP = Math.max(1, ...activityDays.map((d) => d.xp_events));

  $: moodHistory = dashboard?.mood.history ?? [];
  $: maxMood = 5;

  $: topFeatures = dashboard?.usage.top_features ?? [];
  $: maxFeatureCount = Math.max(1, ...topFeatures.map((f) => f.count));

  $: topPages = dashboard?.usage.top_pages ?? [];
  $: maxPageCount = Math.max(1, ...topPages.map((p) => p.count));

  function shortDate(iso: string): string {
    try {
      const d = new Date(iso + 'T00:00:00');
      return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short' });
    } catch {
      return iso;
    }
  }

  async function load() {
    loading = true;
    error = '';
    try {
      dashboard = await api.analytics.dashboard(days);
    } catch (e) {
      error = $t('analytics.error');
      logger.error('[analytics] dashboard load failed:', e);
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    load();
  });

  function changeRange(newDays: number) {
    if (newDays === days) return;
    days = newDays;
    trackFeatureUse('analytics-range');
    load();
  }
</script>

<div class="analytics-page">
  <header class="analytics-header">
    <h1>{$t('analytics.title')}</h1>
    <div class="range-tabs">
      {#each [7, 30, 90] as r}
        <button class="range-tab" class:active={days === r} onclick={() => changeRange(r)}>
          {$t('analytics.lastDays', { values: { n: r } })}
        </button>
      {/each}
    </div>
  </header>

  {#if loading}
    <div class="empty-state">{$t('analytics.loading')}</div>
  {:else if error}
    <div class="empty-state error">{error}</div>
  {:else if dashboard}
    <!-- System overview -->
    <section class="card">
      <h2>{$t('analytics.systemOverview')}</h2>
      <div class="stat-grid">
        <div class="stat">
          <span class="stat-val">{dashboard.system.notes}</span>
          <span class="stat-lab">{$t('analytics.notes')}</span>
        </div>
        <div class="stat">
          <span class="stat-val">{dashboard.system.tags}</span>
          <span class="stat-lab">{$t('analytics.tags')}</span>
        </div>
        <div class="stat">
          <span class="stat-val">{dashboard.system.goals}</span>
          <span class="stat-lab">{$t('analytics.goals')}</span>
        </div>
        <div class="stat">
          <span class="stat-val">{dashboard.system.skills}</span>
          <span class="stat-lab">{$t('analytics.skills')}</span>
        </div>
        <div class="stat">
          <span class="stat-val">{dashboard.system.total_xp.toLocaleString()}</span>
          <span class="stat-lab">{$t('analytics.totalXp')}</span>
        </div>
        <div class="stat">
          <span class="stat-val">{dashboard.system.current_streak}</span>
          <span class="stat-lab">{$t('analytics.streak')}</span>
        </div>
      </div>
    </section>

    <!-- Activity chart -->
    <section class="card">
      <h2>{$t('analytics.activityTitle')}</h2>
      {#if activityDays.length === 0}
        <div class="empty-state mini">{$t('analytics.noData')}</div>
      {:else}
        <div class="bar-chart">
          {#each activityDays as d}
            <div
              class="bar-col"
              title="{shortDate(d.date)} · {d.notes_created}/{$t(
                'analytics.notes'
              )} · {d.xp_events} XP"
            >
              <div class="bar-stack">
                <div
                  class="bar bar-xp"
                  style="height: {Math.max(2, (d.xp_events / maxXP) * 50)}%"
                ></div>
                <div
                  class="bar bar-notes"
                  style="height: {Math.max(2, (d.notes_created / maxNotes) * 50)}%"
                ></div>
              </div>
              <span class="bar-label">{shortDate(d.date).slice(0, 2)}</span>
            </div>
          {/each}
        </div>
        <div class="legend">
          <span class="legend-item"
            ><span class="dot dot-notes"></span>{$t('analytics.notesCreated')}</span
          >
          <span class="legend-item"><span class="dot dot-xp"></span>XP</span>
        </div>
      {/if}
    </section>

    <div class="two-col">
      <!-- Mood trends -->
      <section class="card">
        <h2>{$t('analytics.moodTitle')}</h2>
        {#if moodHistory.length === 0}
          <div class="empty-state mini">{$t('analytics.noData')}</div>
        {:else}
          <div class="mood-stats">
            <div class="stat">
              <span class="stat-val">{dashboard.mood.stats.average.toFixed(1)}</span>
              <span class="stat-lab">{$t('analytics.moodAvg')}</span>
            </div>
            <div class="stat">
              <span class="stat-val">{dashboard.mood.stats.streak}</span>
              <span class="stat-lab">{$t('analytics.moodStreak')}</span>
            </div>
            <div class="stat">
              <span class="stat-val">{dashboard.mood.stats.total_entries}</span>
              <span class="stat-lab">{$t('analytics.moodEntries')}</span>
            </div>
          </div>
          <div class="mood-chart">
            {#each moodHistory as m}
              <div
                class="mood-bar"
                title="{shortDate(m.entry_date)} · {m.score}/5"
                style="height: {(m.score / maxMood) * 100}%"
              ></div>
            {/each}
          </div>
        {/if}
      </section>

      <!-- AI usage -->
      <section class="card">
        <h2>{$t('analytics.aiTitle')}</h2>
        {#if dashboard.ai_usage.ai_enabled}
          <div class="stat-grid">
            <div class="stat">
              <span class="stat-val"
                >${Number(dashboard.ai_usage.estimated_cost_usd || 0).toFixed(2)}</span
              >
              <span class="stat-lab">{$t('analytics.aiCost')}</span>
            </div>
          </div>
          <p class="hint">{$t('analytics.aiMonthly')}</p>
        {:else}
          <div class="empty-state mini">{$t('analytics.aiUnavailable')}</div>
        {/if}
      </section>
    </div>

    <div class="two-col">
      <!-- Feature usage -->
      <section class="card">
        <h2>{$t('analytics.featureUsage')}</h2>
        {#if topFeatures.length === 0}
          <div class="empty-state mini">{$t('analytics.noData')}</div>
        {:else}
          <div class="hbar-list">
            {#each topFeatures as f}
              <div class="hbar-row">
                <span class="hbar-label">{f.feature}</span>
                <div class="hbar-track">
                  <div class="hbar-fill" style="width: {(f.count / maxFeatureCount) * 100}%"></div>
                </div>
                <span class="hbar-val">{f.count}</span>
              </div>
            {/each}
          </div>
        {/if}
      </section>

      <!-- Session stats -->
      <section class="card">
        <h2>{$t('analytics.sessionStats')}</h2>
        <div class="stat-grid">
          <div class="stat">
            <span class="stat-val">{dashboard.usage.session_count}</span>
            <span class="stat-lab">{$t('analytics.sessions')}</span>
          </div>
          <div class="stat">
            <span class="stat-val">{dashboard.usage.active_days}</span>
            <span class="stat-lab">{$t('analytics.activeDays')}</span>
          </div>
          <div class="stat">
            <span class="stat-val">{dashboard.usage.avg_session_duration_min.toFixed(1)}</span>
            <span class="stat-lab">{$t('analytics.avgSessionMin')}</span>
          </div>
          <div class="stat">
            <span class="stat-val">{dashboard.usage.total_events}</span>
            <span class="stat-lab">{$t('analytics.totalEvents')}</span>
          </div>
        </div>
        {#if topPages.length > 0}
          <h3 class="sub-title">{$t('analytics.topPages')}</h3>
          <div class="hbar-list">
            {#each topPages as p}
              <div class="hbar-row">
                <span class="hbar-label">{p.path}</span>
                <div class="hbar-track">
                  <div
                    class="hbar-fill hbar-fill-alt"
                    style="width: {(p.count / maxPageCount) * 100}%"
                  ></div>
                </div>
                <span class="hbar-val">{p.count}</span>
              </div>
            {/each}
          </div>
        {/if}
      </section>
    </div>
  {/if}
</div>

<style>
  .analytics-page {
    padding: var(--s4);
    max-width: 1100px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: var(--s4);
  }

  .analytics-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--s3);
  }

  .analytics-header h1 {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
    letter-spacing: 0.04em;
  }

  .range-tabs {
    display: flex;
    gap: 4px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 2px;
  }

  .range-tab {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 11px;
    padding: 4px 10px;
    border-radius: var(--r-sm);
    cursor: pointer;
    transition:
      background var(--t-fast),
      color var(--t-fast);
  }

  .range-tab:hover {
    color: var(--text-primary);
  }

  .range-tab.active {
    background: color-mix(in srgb, var(--xp) 18%, transparent);
    color: var(--xp);
  }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: var(--s4);
  }

  .card h2 {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    margin: 0 0 var(--s3);
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }

  .sub-title {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    margin: var(--s4) 0 var(--s2);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
    gap: var(--s3);
  }

  .stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .stat-val {
    font-size: 22px;
    font-weight: 700;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
  }

  .stat-lab {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .two-col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s4);
  }

  @media (max-width: 720px) {
    .two-col {
      grid-template-columns: 1fr;
    }
  }

  /* Activity bar chart */
  .bar-chart {
    display: flex;
    align-items: flex-end;
    gap: 3px;
    height: 120px;
  }

  .bar-col {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    height: 100%;
  }

  .bar-stack {
    flex: 1;
    display: flex;
    flex-direction: column-reverse;
    gap: 2px;
    width: 100%;
    justify-content: flex-end;
  }

  .bar {
    width: 100%;
    border-radius: var(--r-sm);
    min-height: 2px;
  }

  .bar-notes {
    background: color-mix(in srgb, var(--xp) 70%, transparent);
  }

  .bar-xp {
    background: color-mix(in srgb, var(--info) 60%, transparent);
  }

  .bar-label {
    font-size: 9px;
    color: var(--text-disabled);
    white-space: nowrap;
    overflow: hidden;
  }

  .legend {
    display: flex;
    gap: var(--s4);
    margin-top: var(--s3);
    font-size: 10px;
    color: var(--text-muted);
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 2px;
  }

  .dot-notes {
    background: color-mix(in srgb, var(--xp) 70%, transparent);
  }

  .dot-xp {
    background: color-mix(in srgb, var(--info) 60%, transparent);
  }

  /* Mood chart */
  .mood-stats {
    display: flex;
    gap: var(--s4);
    margin-bottom: var(--s3);
  }

  .mood-chart {
    display: flex;
    align-items: flex-end;
    gap: 3px;
    height: 80px;
  }

  .mood-bar {
    flex: 1;
    min-width: 0;
    background: color-mix(in srgb, var(--success) 60%, transparent);
    border-radius: var(--r-sm);
    min-height: 4px;
  }

  /* Horizontal bar lists */
  .hbar-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .hbar-row {
    display: flex;
    align-items: center;
    gap: var(--s2);
    font-size: 11px;
  }

  .hbar-label {
    width: 90px;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .hbar-track {
    flex: 1;
    height: 6px;
    background: var(--hover);
    border-radius: var(--r-full);
    overflow: hidden;
  }

  .hbar-fill {
    height: 100%;
    background: var(--xp);
    border-radius: var(--r-full);
    transition: width var(--t-normal);
  }

  .hbar-fill-alt {
    background: var(--info);
  }

  .hbar-val {
    width: 28px;
    text-align: right;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }

  .hint {
    font-size: 10px;
    color: var(--text-disabled);
    margin: var(--s2) 0 0;
  }

  .empty-state {
    color: var(--text-muted);
    font-size: 13px;
    padding: var(--s6);
    text-align: center;
  }

  .empty-state.mini {
    padding: var(--s4);
    font-size: 11px;
  }

  .empty-state.error {
    color: var(--error);
  }
</style>
