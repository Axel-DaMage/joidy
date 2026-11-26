<script lang="ts">
  import { onMount } from 'svelte';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import { TriangleAlert } from 'lucide-svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import {
    formatActivityDateTime,
    formatDistance,
    formatDuration,
    formatElevation,
    formatNumber,
    formatPace,
    formatSpeed,
    sportCategory,
    sportCategoryKey,
    sportIconName,
  } from '$lib/strava/format';
  import {
    buildElevationGeometry,
    buildRoutePath,
    decodePolyline,
    getLatLngSeries,
    getNumberSeries,
  } from '$lib/strava/streams';
  import { api } from '$lib/api';
  import { locale } from '$lib/stores/locale';
  import { logger } from '$lib/utils/logger';
  import { stravaErrorKind } from '$lib/strava/errors';
  import { t } from 'svelte-i18n';
  import type { StravaActivity, StravaStreams } from '$lib/strava/types';

  interface Props {
    activityId: number;
  }

  let { activityId }: Props = $props();

  let activity = $state<StravaActivity | null>(null);
  let streams = $state<StravaStreams | null>(null);
  let loading = $state(true);
  let loadError = $state('');

  const CHART_W = 640;
  const CHART_H = 160;

  const category = $derived(sportCategory(activity?.sport_type, activity?.type));
  const sportLabel = $derived($t(`strava.${sportCategoryKey(category)}`));

  // Route trace: prefer the latlng stream (full resolution), fall back to the
  // detail's summary_polyline when streams didn't include GPS.
  const routePoints = $derived.by((): [number, number][] => {
    const fromStream = streams ? getLatLngSeries(streams) : [];
    if (fromStream.length >= 2) return fromStream;
    const encoded = activity?.map?.summary_polyline;
    if (encoded) return decodePolyline(encoded);
    return [];
  });

  const routePath = $derived(buildRoutePath(routePoints, CHART_W, CHART_H));
  const hasRoute = $derived(routePath.length > 0);

  const altitude = $derived(streams ? getNumberSeries(streams, 'altitude') : []);
  const elevation = $derived(buildElevationGeometry(altitude, CHART_W, CHART_H));
  const hasElevation = $derived(elevation.line.length > 0);

  const splits = $derived(activity?.splits_metric ?? []);
  const laps = $derived(activity?.laps ?? []);

  // Heart-rate / power mini-profiles reuse the same SVG pipeline.
  const heartrate = $derived(streams ? getNumberSeries(streams, 'heartrate') : []);
  const watts = $derived(streams ? getNumberSeries(streams, 'watts') : []);
  const hrGeo = $derived(buildElevationGeometry(heartrate, CHART_W, 90));
  const powerGeo = $derived(buildElevationGeometry(watts, CHART_W, 90));

  const paceLabel = $derived(
    formatPace(activity?.moving_time, activity?.distance) ?? '—'
  );

  onMount(async () => {
    loading = true;
    loadError = '';
    try {
      const [detail, streamData] = await Promise.all([
        api.strava.activity(activityId),
        api.strava.activityStreams(activityId).catch((e) => {
          // Streams are best-effort: a 404/429 shouldn't kill the whole detail.
          logger.warn('strava streams fetch failed', e);
          return null;
        }),
      ]);
      activity = detail;
      streams = streamData;
    } catch (e) {
      logger.error('strava activity detail failed', e);
      loadError = $t(`strava.errors.${stravaErrorKind(e)}`);
    } finally {
      loading = false;
    }
  });

  function splitPace(split: { moving_time?: number; distance?: number }): string {
    return formatPace(split.moving_time, split.distance) ?? '—';
  }

  function fmtSplitTime(sec?: number): string {
    return formatDuration(sec);
  }
</script>

<div class="strava-detail">
  {#if loading}
    <div class="loading caption">{$t('strava.detail.loading')}</div>
  {:else if loadError || !activity}
    <EmptyState title={$t('strava.detail.loadFailed')} message={loadError}>
      {#snippet icon()}<TriangleAlert size={40} />{/snippet}
    </EmptyState>
  {:else}
    <!-- Header -->
    <div class="detail-header">
      <div class="detail-icon">
        <DynamicIcon name={sportIconName(category)} size={22} />
      </div>
      <div class="detail-title-block">
        <h3 class="detail-name">{activity.name || $t('strava.untitledActivity')}</h3>
        <div class="detail-sub caption">
          {sportLabel} · {formatActivityDateTime(activity.start_date, $locale)}
          {#if activity.timezone}<span class="tz">({activity.timezone})</span>{/if}
        </div>
      </div>
    </div>

    <!-- Metric grid -->
    <div class="metrics-grid">
      <div class="metric-cell">
        <span class="metric-value mono">{formatDistance(activity.distance, $locale)}</span>
        <span class="metric-label">{$t('strava.metrics.distance')}</span>
      </div>
      <div class="metric-cell">
        <span class="metric-value mono">{formatDuration(activity.moving_time)}</span>
        <span class="metric-label">{$t('strava.metrics.movingTime')}</span>
      </div>
      <div class="metric-cell">
        <span class="metric-value mono">{formatDuration(activity.elapsed_time)}</span>
        <span class="metric-label">{$t('strava.metrics.elapsedTime')}</span>
      </div>
      <div class="metric-cell">
        <span class="metric-value mono">{paceLabel}</span>
        <span class="metric-label">{$t('strava.metrics.pace')}</span>
      </div>
      <div class="metric-cell">
        <span class="metric-value mono">{formatSpeed(
          activity.distance != null && activity.moving_time
            ? activity.distance / activity.moving_time
            : null,
          $locale
        )}</span>
        <span class="metric-label">{$t('strava.metrics.avgSpeed')}</span>
      </div>
      <div class="metric-cell">
        <span class="metric-value mono">{formatElevation(
          activity.total_elevation_gain,
          $locale
        )}</span>
        <span class="metric-label">{$t('strava.metrics.elevation')}</span>
      </div>
      {#if activity.calories != null}
        <div class="metric-cell">
          <span class="metric-value mono">{formatNumber(activity.calories, $locale)} kcal</span>
          <span class="metric-label">{$t('strava.metrics.calories')}</span>
        </div>
      {/if}
      {#if activity.average_heartrate != null}
        <div class="metric-cell">
          <span class="metric-value mono">{Math.round(activity.average_heartrate)} bpm</span>
          <span class="metric-label">{$t('strava.metrics.avgHr')}</span>
        </div>
      {/if}
      {#if activity.max_heartrate != null}
        <div class="metric-cell">
          <span class="metric-value mono">{Math.round(activity.max_heartrate)} bpm</span>
          <span class="metric-label">{$t('strava.metrics.maxHr')}</span>
        </div>
      {/if}
      {#if activity.average_watts != null}
        <div class="metric-cell">
          <span class="metric-value mono">{Math.round(activity.average_watts)} W</span>
          <span class="metric-label">{$t('strava.metrics.avgPower')}</span>
        </div>
      {/if}
    </div>

    <!-- Route trace -->
    <section class="detail-section">
      <h4 class="section-title">{$t('strava.detail.route')}</h4>
      {#if hasRoute}
        <svg
          class="route-svg"
          viewBox="0 0 {CHART_W} {CHART_H}"
          role="img"
          aria-label={$t('strava.detail.routeAria')}
          preserveAspectRatio="xMidYMid meet"
        >
          <path d={routePath} fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
        </svg>
      {:else}
        <p class="no-data caption">{$t('strava.detail.noRoute')}</p>
      {/if}
    </section>

    <!-- Elevation profile -->
    <section class="detail-section">
      <h4 class="section-title">
        {$t('strava.detail.elevation')}
        {#if hasElevation}
          <span class="chart-range caption">
            {elevation.min}–{elevation.max} m
          </span>
        {/if}
      </h4>
      {#if hasElevation}
        <svg
          class="chart-svg"
          viewBox="0 0 {CHART_W} {CHART_H}"
          role="img"
          aria-label={$t('strava.detail.elevationAria')}
          preserveAspectRatio="none"
        >
          <path d={elevation.area} fill="color-mix(in srgb, var(--accent) 18%, transparent)" />
          <path d={elevation.line} fill="none" stroke="var(--accent)" stroke-width="1.5" />
        </svg>
      {:else}
        <p class="no-data caption">{$t('strava.detail.noElevation')}</p>
      {/if}
    </section>

    <!-- Heart rate / power profiles (when streams carry them) -->
    {#if hrGeo.line}
      <section class="detail-section">
        <h4 class="section-title">{$t('strava.detail.heartRate')}</h4>
        <svg class="chart-svg" viewBox="0 0 {CHART_W} 90" role="img" aria-label={$t('strava.detail.heartRateAria')} preserveAspectRatio="none">
          <path d={hrGeo.area} fill="color-mix(in srgb, #e5484d 16%, transparent)" />
          <path d={hrGeo.line} fill="none" stroke="#e5484d" stroke-width="1.5" />
        </svg>
      </section>
    {/if}
    {#if powerGeo.line}
      <section class="detail-section">
        <h4 class="section-title">{$t('strava.detail.power')}</h4>
        <svg class="chart-svg" viewBox="0 0 {CHART_W} 90" role="img" aria-label={$t('strava.detail.powerAria')} preserveAspectRatio="none">
          <path d={powerGeo.area} fill="color-mix(in srgb, #f5a524 16%, transparent)" />
          <path d={powerGeo.line} fill="none" stroke="#f5a524" stroke-width="1.5" />
        </svg>
      </section>
    {/if}

    <!-- Splits -->
    {#if splits.length > 0}
      <section class="detail-section">
        <h4 class="section-title">
          {$t('strava.detail.splits')} <span class="chart-range caption">({splits.length})</span>
        </h4>
        <div class="splits-table-wrap">
          <table class="splits-table">
            <thead>
              <tr>
                <th>{$t('strava.detail.splitDistance')}</th>
                <th>{$t('strava.metrics.time')}</th>
                <th>{$t('strava.metrics.pace')}</th>
                <th>{$t('strava.detail.elevDelta')}</th>
                <th>{$t('strava.metrics.avgHr')}</th>
              </tr>
            </thead>
            <tbody>
              {#each splits as split, i (i)}
                <tr>
                  <td class="mono">{split.distance != null
                      ? formatDistance(split.distance, $locale)
                      : i + 1}</td>
                  <td class="mono">{fmtSplitTime(split.moving_time)}</td>
                  <td class="mono">{splitPace(split)}</td>
                  <td class="mono">
                    {split.elevation_difference != null
                      ? `${split.elevation_difference > 0 ? '+' : ''}${Math.round(split.elevation_difference)} m`
                      : '—'}
                  </td>
                  <td class="mono">
                    {split.heart_rate != null ? `${Math.round(split.heart_rate)} bpm` : '—'}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    {/if}

    <!-- Laps (only when the activity was recorded with lap buttons) -->
    {#if laps.length > 0 && splits.length === 0}
      <section class="detail-section">
        <h4 class="section-title">
          {$t('strava.detail.laps')} <span class="chart-range caption">({laps.length})</span>
        </h4>
        <div class="splits-table-wrap">
          <table class="splits-table">
            <thead>
              <tr>
                <th>{$t('strava.detail.lap')}</th>
                <th>{$t('strava.metrics.distance')}</th>
                <th>{$t('strava.metrics.time')}</th>
                <th>{$t('strava.metrics.pace')}</th>
                <th>{$t('strava.metrics.elevation')}</th>
              </tr>
            </thead>
            <tbody>
              {#each laps as lap, i (i)}
                <tr>
                  <td>{lap.name || i + 1}</td>
                  <td class="mono">{formatDistance(lap.distance, $locale)}</td>
                  <td class="mono">{fmtSplitTime(lap.moving_time)}</td>
                  <td class="mono">{splitPace(lap)}</td>
                  <td class="mono">{formatElevation(lap.total_elevation_gain, $locale)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    {/if}
  {/if}
</div>

<style>
  .strava-detail {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .loading {
    text-align: center;
    padding: 32px 0;
    color: var(--text-muted);
  }

  .detail-header {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .detail-icon {
    flex-shrink: 0;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    color: var(--accent);
  }

  .detail-name {
    margin: 0;
    font-size: 16px;
    color: var(--text-primary);
  }

  .detail-sub {
    color: var(--text-muted);
    margin-top: 2px;
  }

  .tz {
    opacity: 0.7;
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
    gap: 8px;
  }

  .metric-cell {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--bg);
  }

  .metric-value {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .metric-label {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .detail-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .section-title {
    margin: 0;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  .chart-range {
    text-transform: none;
    letter-spacing: 0;
  }

  .route-svg {
    width: 100%;
    height: 180px;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--bg);
  }

  .chart-svg {
    width: 100%;
    height: 140px;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--bg);
  }

  .no-data {
    color: var(--text-muted);
    padding: 8px 0;
  }

  .splits-table-wrap {
    max-height: 260px;
    overflow-y: auto;
    border: 1px solid var(--border);
    border-radius: 10px;
  }

  .splits-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  .splits-table th {
    position: sticky;
    top: 0;
    background: var(--surface);
    text-align: left;
    padding: 8px 10px;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--border);
  }

  .splits-table td {
    padding: 6px 10px;
    border-bottom: 1px solid var(--border-light);
    color: var(--text-secondary);
  }

  .splits-table tr:last-child td {
    border-bottom: none;
  }
</style>
