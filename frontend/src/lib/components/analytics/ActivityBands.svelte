<script lang="ts">
  import Sun from 'lucide-svelte/icons/sun';
  import Moon from 'lucide-svelte/icons/moon';
  import Sunrise from 'lucide-svelte/icons/sunrise';
  import Sunset from 'lucide-svelte/icons/sunset';
  import ChartCard from './ChartCard.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { cellValue } from '$lib/utils/insights';
  import { t } from 'svelte-i18n';

  // Daypart share tile (#1499): what fraction of the XP earned falls into
  // each 6-hour band — the horizontal companion to the radial clock.
  type Seasonality = AnalyticsOverview['seasonality'];

  let { seasonality }: { seasonality?: Seasonality } = $props();

  const BANDS = [
    { key: 'night', from: 0, to: 6, icon: Moon },
    { key: 'morning', from: 6, to: 12, icon: Sunrise },
    { key: 'afternoon', from: 12, to: 18, icon: Sun },
    { key: 'evening', from: 18, to: 24, icon: Sunset },
  ] as const;

  let shares = $derived.by(() => {
    const cells = seasonality?.cells ?? [];
    const sums = BANDS.map((b) =>
      cells.reduce((acc, c) => (c.hour >= b.from && c.hour < b.to ? acc + cellValue(c) : acc), 0)
    );
    const total = sums.reduce((a, b) => a + b, 0);
    const top = Math.max(...sums);
    return BANDS.map((b, i) => ({
      ...b,
      range: `${String(b.from).padStart(2, '0')}–${String(b.to).padStart(2, '0')}h`,
      pct: total > 0 ? Math.round((sums[i] / total) * 100) : 0,
      top: total > 0 && sums[i] === top,
    }));
  });
  let hasData = $derived(shares.some((s) => s.pct > 0));
</script>

<ChartCard title={$t('analyticsPage.bands.title')}>
  {#snippet icon()}<Sun size={13} />{/snippet}

  {#if !hasData}
    <div class="chart-empty"><span>{$t('analyticsPage.seasonality.empty')}</span></div>
  {:else}
    <div class="bands">
      {#each shares as band, i (band.key)}
        {@const Icon = band.icon}
        <div class="band-row" class:top={band.top} style:--i={i}>
          <span class="band-icon"><Icon size={14} /></span>
          <div class="band-main">
            <div class="band-head">
              <span class="band-name">{$t(`analyticsPage.bands.${band.key}`)}</span>
              <span class="band-hours mono">{band.range}</span>
              <span class="band-pct mono">{band.pct}%</span>
            </div>
            <div class="band-track">
              <div class="band-fill" style:width="{Math.max(2, band.pct)}%"></div>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</ChartCard>

<style>
  .bands {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-around;
    gap: var(--s2);
  }
  .band-row {
    display: flex;
    align-items: center;
    gap: var(--s3);
  }
  .band-icon {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: var(--r);
    border: 1px solid var(--border);
    flex-shrink: 0;
    color: var(--text-muted);
  }
  .band-row.top .band-icon {
    color: var(--xp);
    border-color: var(--xp);
  }
  .band-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .band-head {
    display: flex;
    align-items: baseline;
    gap: var(--s2);
  }
  .band-name {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }
  .band-row.top .band-fill {
    background: var(--xp);
  }
  .band-row.top .band-name {
    color: var(--xp);
  }
  .band-hours {
    font-size: 10px;
    color: var(--text-muted);
  }
  .band-pct {
    margin-left: auto;
    font-size: 12px;
    font-weight: 800;
    color: var(--text-primary);
  }
  .band-track {
    height: 6px;
    border-radius: 3px;
    background: color-mix(in srgb, var(--text-primary) 7%, transparent);
    overflow: hidden;
  }
  .band-fill {
    height: 100%;
    border-radius: 3px;
    background: color-mix(in srgb, var(--xp) 55%, transparent);
    transform-origin: left;
    animation: band-grow 0.8s cubic-bezier(0.2, 0.7, 0.2, 1) both;
    animation-delay: calc(var(--i) * 70ms);
  }
  .chart-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    font-size: 12px;
  }
  @keyframes band-grow {
    from {
      transform: scaleX(0);
    }
    to {
      transform: scaleX(1);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .band-fill {
      animation: none;
    }
  }
</style>
