<script lang="ts">
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import {
    formatDistance,
    formatDurationLong,
    formatNumber,
    mergeSportTotals,
    summarizeActivities,
  } from '$lib/strava/format';
  import { locale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';
  import type { StravaActivity, StravaStats } from '$lib/strava/types';

  interface Props {
    stats: StravaStats | null;
    activities: StravaActivity[];
    loading?: boolean;
  }

  let { stats, activities, loading = false }: Props = $props();

  const summary = $derived(summarizeActivities(activities));

  const ytdTotals = $derived(
    mergeSportTotals(stats?.ytd_ride_totals, stats?.ytd_run_totals, stats?.ytd_swim_totals)
  );
  const allTotals = $derived(
    mergeSportTotals(stats?.all_ride_totals, stats?.all_run_totals, stats?.all_swim_totals)
  );

  // Last 6 ISO weeks with activity, for the mini bar strip.
  const recentWeeks = $derived(summary.byWeek.slice(0, 6));
  const maxWeekDistance = $derived(
    recentWeeks.reduce((m, w) => Math.max(m, w.totals.distance), 0)
  );

  function weekLabel(key: string): string {
    // "2026-W06" → "S06" / "W06" — compact; full label via title attr.
    return key.split('-W')[1] ?? key;
  }

  function weekTitle(key: string): string {
    const [year, week] = key.split('-W');
    return `${year} · W${week}`;
  }

  interface PeriodCard {
    key: string;
    icon: string;
    distance: number;
    movingTime: number;
    count?: number;
    calories?: number;
  }

  const periodCards = $derived<PeriodCard[]>([
    {
      key: 'week',
      icon: 'Calendar',
      distance: summary.thisWeek.distance,
      movingTime: summary.thisWeek.movingTime,
      count: summary.thisWeek.count,
      calories: summary.thisWeek.calories,
    },
    {
      key: 'month',
      icon: 'CalendarDays',
      distance: summary.thisMonth.distance,
      movingTime: summary.thisMonth.movingTime,
      count: summary.thisMonth.count,
      calories: summary.thisMonth.calories,
    },
    {
      key: 'ytd',
      icon: 'TrendingUp',
      distance: ytdTotals.distance ?? 0,
      movingTime: ytdTotals.moving_time ?? 0,
      count: ytdTotals.count,
    },
    {
      key: 'all',
      icon: 'Trophy',
      distance: allTotals.distance ?? 0,
      movingTime: allTotals.moving_time ?? 0,
      count: allTotals.count,
    },
  ]);

  function hasAnyData(): boolean {
    return periodCards.some(
      (c) => (c.distance ?? 0) > 0 || (c.movingTime ?? 0) > 0 || (c.count ?? 0) > 0
    );
  }
</script>

<section class="strava-stats" aria-label={$t('strava.stats.title')}>
  <h3 class="stats-title">{$t('strava.stats.title')}</h3>

  {#if loading}
    <div class="loading caption">{$t('strava.stats.loading')}</div>
  {:else if !hasAnyData()}
    <p class="no-data caption">{$t('strava.stats.empty')}</p>
  {:else}
    <div class="period-grid">
      {#each periodCards as card (card.key)}
        <div class="period-card">
          <div class="period-head">
            <DynamicIcon name={card.icon} size={13} />
            <span class="period-label">{$t(`strava.stats.${card.key}`)}</span>
          </div>
          <span class="period-distance mono">
            {formatDistance(card.distance, $locale)}
          </span>
          <span class="period-sub mono">
            {formatDurationLong(card.movingTime)}
            {#if card.count != null && card.count > 0}
              · {formatNumber(card.count, $locale)} {$t('strava.stats.activities')}
            {/if}
          </span>
          {#if card.calories != null && card.calories > 0}
            <span class="period-sub mono">
              {formatNumber(card.calories, $locale)} kcal
            </span>
          {/if}
        </div>
      {/each}
    </div>

    {#if recentWeeks.length > 1}
      <div class="weeks-strip">
        <span class="weeks-title caption">{$t('strava.stats.byWeek')}</span>
        <div class="weeks-bars">
          {#each recentWeeks as week (week.key)}
            {@const pct = maxWeekDistance > 0 ? Math.max((week.totals.distance / maxWeekDistance) * 100, 2) : 0}
            <div class="week-col" title="{weekTitle(week.key)} — {formatDistance(week.totals.distance, $locale)}">
              <div class="week-bar" style="height: {pct}%"></div>
              <span class="week-label mono">{weekLabel(week.key)}</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</section>

<style>
  .strava-stats {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .stats-title {
    margin: 0;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .loading,
  .no-data {
    color: var(--text-muted);
    padding: 8px 0;
  }

  .period-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 10px;
  }

  .period-card {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 12px 14px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface);
  }

  .period-head {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--accent);
  }

  .period-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .period-distance {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .period-sub {
    font-size: 11px;
    color: var(--text-muted);
  }

  .weeks-strip {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px 14px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface);
  }

  .weeks-title {
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .weeks-bars {
    display: flex;
    align-items: flex-end;
    gap: 8px;
    height: 56px;
  }

  .week-col {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    height: 100%;
    justify-content: flex-end;
  }

  .week-bar {
    width: 100%;
    max-width: 42px;
    border-radius: 4px 4px 0 0;
    background: color-mix(in srgb, var(--accent) 55%, transparent);
    min-height: 2px;
  }

  .week-label {
    font-size: 9px;
    color: var(--text-muted);
  }
</style>
