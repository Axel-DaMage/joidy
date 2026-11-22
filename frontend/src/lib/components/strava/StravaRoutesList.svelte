<script lang="ts">
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import {
    formatActivityDate,
    formatDistance,
    formatElevation,
  } from '$lib/strava/format';
  import { buildRoutePath, decodePolyline } from '$lib/strava/streams';
  import { locale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';
  import type { StravaRoute } from '$lib/strava/types';

  interface Props {
    routes: StravaRoute[];
    loading?: boolean;
    loadError?: string;
    onretry?: () => void;
  }

  let { routes, loading = false, loadError = '', onretry }: Props = $props();

  const MAP_W = 120;
  const MAP_H = 56;

  // Strava route types: 1 = ride, 2 = run, 3 = other (water/etc).
  function routeIcon(route: StravaRoute): string {
    if (route.type === 2) return 'Footprints';
    if (route.type === 1) return 'Bike';
    return 'Route';
  }

  function routePath(route: StravaRoute): string {
    const encoded = route.map?.summary_polyline;
    if (!encoded) return '';
    return buildRoutePath(decodePolyline(encoded), MAP_W, MAP_H, 4);
  }

  function routeDistance(route: StravaRoute): string {
    return formatDistance(route.distance, $locale);
  }

  function routeElevation(route: StravaRoute): string {
    return formatElevation(route.elevation_gain, $locale);
  }

  function routeDate(route: StravaRoute): string {
    return formatActivityDate(route.created_at, $locale);
  }
</script>

<section class="strava-routes" aria-label={$t('strava.routes.title')}>
  <h3 class="routes-title">{$t('strava.routes.title')}</h3>

  {#if loading}
    <div class="loading caption">{$t('strava.routes.loading')}</div>
  {:else if loadError}
    <EmptyState
      title={$t('strava.routes.loadFailed')}
      message={loadError}
      actionLabel={onretry ? $t('common.retry') : ''}
      onAction={onretry ?? null}
    >
      {#snippet icon()}<DynamicIcon name="TriangleAlert" size={40} />{/snippet}
    </EmptyState>
  {:else if routes.length === 0}
    <EmptyState title={$t('strava.routes.empty')} message={$t('strava.routes.emptyHint')}>
      {#snippet icon()}<DynamicIcon name="Map" size={40} />{/snippet}
    </EmptyState>
  {:else}
    <div class="routes-grid">
      {#each routes as route (route.id)}
        {@const d = routePath(route)}
        <div class="route-card">
          <div class="route-map">
            {#if d}
              <svg viewBox="0 0 {MAP_W} {MAP_H}" role="img" aria-label={route.name ?? $t('strava.routes.routeAria')} preserveAspectRatio="xMidYMid meet">
                <path d={d} fill="none" stroke="var(--accent)" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" />
              </svg>
            {:else}
              <div class="route-map-empty"><DynamicIcon name="Map" size={20} /></div>
            {/if}
          </div>
          <div class="route-info">
            <div class="route-name">{route.name || $t('strava.routes.unnamed')}</div>
            <div class="route-meta caption">
              <span><DynamicIcon name={routeIcon(route)} size={11} /> {routeDistance(route)}</span>
              <span title={$t('strava.metrics.elevation')}>{routeElevation(route)}</span>
              {#if routeDate(route)}<span>{routeDate(route)}</span>{/if}
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</section>

<style>
  .strava-routes {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .routes-title {
    margin: 0;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .loading {
    color: var(--text-muted);
    padding: 16px 0;
  }

  .routes-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 10px;
  }

  .route-card {
    display: flex;
    gap: 10px;
    padding: 10px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface);
    align-items: center;
  }

  .route-map {
    flex-shrink: 0;
    width: 120px;
    height: 56px;
    border-radius: 8px;
    border: 1px solid var(--border-light);
    background: var(--bg);
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .route-map svg {
    width: 100%;
    height: 100%;
  }

  .route-map-empty {
    color: var(--text-muted);
    opacity: 0.5;
  }

  .route-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .route-name {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .route-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    color: var(--text-muted);
  }

  .route-meta span {
    display: inline-flex;
    align-items: center;
    gap: 3px;
  }
</style>
