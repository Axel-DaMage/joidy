<script lang="ts">
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import {
    formatActivityDate,
    formatDistance,
    formatDuration,
    formatPace,
    sportCategory,
    sportCategoryKey,
    sportIconName,
  } from '$lib/strava/format';
  import { locale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';
  import type { StravaActivity } from '$lib/strava/types';

  interface Props {
    activity: StravaActivity;
    onselect?: (id: number) => void;
  }

  let { activity, onselect }: Props = $props();

  const category = $derived(sportCategory(activity.sport_type, activity.type));
  const iconName = $derived(sportIconName(category));
  const sportLabel = $derived($t(`strava.${sportCategoryKey(category)}`));

  const distanceLabel = $derived(formatDistance(activity.distance, $locale));
  const timeLabel = $derived(formatDuration(activity.moving_time));
  const paceLabel = $derived(formatPace(activity.moving_time, activity.distance) ?? '—');
  const elevationLabel = $derived(
    activity.total_elevation_gain != null
      ? `${Math.round(activity.total_elevation_gain).toLocaleString($locale)} m`
      : null
  );
  const caloriesLabel = $derived(
    activity.calories != null
      ? `${Math.round(activity.calories).toLocaleString($locale)} kcal`
      : null
  );

  function handleClick() {
    onselect?.(activity.id);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="strava-card"
  role="button"
  tabindex="0"
  onclick={handleClick}
  onkeydown={handleKeydown}
  aria-label="{activity.name ?? $t('strava.activityFallback')} — {distanceLabel}"
>
  <div class="card-icon">
    <DynamicIcon name={iconName} size={20} />
  </div>
  <div class="card-main">
    <div class="card-top">
      <span class="card-name">{activity.name || $t('strava.untitledActivity')}</span>
      <span class="card-date">{formatActivityDate(activity.start_date, $locale)}</span>
    </div>
    <div class="card-sport caption">{sportLabel}</div>
    <div class="card-metrics">
      <span class="metric" title={$t('strava.metrics.distance')}>
        <DynamicIcon name="Route" size={12} /> {distanceLabel}
      </span>
      <span class="metric" title={$t('strava.metrics.time')}>
        <DynamicIcon name="Timer" size={12} /> {timeLabel}
      </span>
      <span class="metric" title={$t('strava.metrics.pace')}>
        <DynamicIcon name="Gauge" size={12} /> {paceLabel}
      </span>
      {#if elevationLabel}
        <span class="metric" title={$t('strava.metrics.elevation')}>
          <DynamicIcon name="TrendingUp" size={12} /> {elevationLabel}
        </span>
      {/if}
      {#if caloriesLabel}
        <span class="metric" title={$t('strava.metrics.calories')}>
          <DynamicIcon name="Flame" size={12} /> {caloriesLabel}
        </span>
      {/if}
    </div>
  </div>
</div>

<style>
  .strava-card {
    display: flex;
    gap: 12px;
    padding: 12px 14px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface);
    cursor: pointer;
    transition:
      border-color 0.15s ease,
      transform 0.15s ease;
  }

  .strava-card:hover {
    border-color: var(--accent);
    transform: translateY(-1px);
  }

  .strava-card:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 2px;
  }

  .card-icon {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    color: var(--accent);
  }

  .card-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .card-top {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
  }

  .card-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .card-date {
    flex-shrink: 0;
    font-size: 11px;
    color: var(--text-muted);
  }

  .card-sport {
    color: var(--text-muted);
  }

  .card-metrics {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 4px;
  }

  .metric {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--text-secondary);
  }
</style>
