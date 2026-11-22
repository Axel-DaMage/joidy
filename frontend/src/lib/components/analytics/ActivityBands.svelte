<script lang="ts">
  import ChartCard from './ChartCard.svelte';
  import Sun from 'lucide-svelte/icons/sun';
  import type { AnalyticsOverview } from '$lib/api';
  import { t } from 'svelte-i18n';

  // Daypart share tile (#1499): what fraction of activity falls into each
  // 6-hour band — the horizontal companion to the radial clock.
  type Seasonality = AnalyticsOverview['seasonality'];

  let { seasonality }: { seasonality?: Seasonality } = $props();

  const BANDS = [
    { key: 'night', from: 0, to: 6 },
    { key: 'morning', from: 6, to: 12 },
    { key: 'afternoon', from: 12, to: 18 },
    { key: 'evening', from: 18, to: 24 },
  ] as const;

  let shares = $derived.by(() => {
    const cells = seasonality?.cells ?? [];
    const sums = BANDS.map((b) =>
      cells.reduce((acc, c) => (c.hour >= b.from && c.hour < b.to ? acc + c.count : acc), 0)
    );
    const total = sums.reduce((a, b) => a + b, 0);
    return BANDS.map((b, i) => ({
      key: b.key,
      range: `${b.from}–${b.to}h`,
      pct: total > 0 ? Math.round((sums[i] / total) * 100) : 0,
    }));
  });
  let hasData = $derived(shares.some((s) => s.pct > 0));
</script>

<ChartCard title={$t('goalsAnalytics.bands.title')}>
  {#snippet icon()}<Sun size={15} />{/snippet}

  {#if !hasData}
    <div class="chart-empty"><span>{$t('goalsAnalytics.seasonality.empty')}</span></div>
  {:else}
    <div class="bands">
      {#each shares as band (band.key)}
        <div class="band-row">
          <span class="band-name">{$t(`goalsAnalytics.bands.${band.key}`)}</span>
          <div class="band-track">
            <div class="band-fill" style:width="{band.pct}%"></div>
          </div>
          <span class="band-pct mono">{band.pct}%</span>
        </div>
        <span class="band-hours mono">{band.range}</span>
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
    justify-content: center;
    gap: 2px;
  }
  .band-row {
    display: flex;
    align-items: center;
    gap: var(--s2);
  }
  .band-name {
    width: 74px;
    flex-shrink: 0;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    font-family: var(--font-mono);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .band-track {
    flex: 1;
    height: 8px;
    border-radius: 4px;
    background: color-mix(in srgb, var(--text-primary) 8%, transparent);
    overflow: hidden;
  }
  .band-fill {
    height: 100%;
    border-radius: 4px;
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--xp) 60%, transparent),
      var(--xp)
    );
    transition: width 0.4s ease;
  }
  .band-pct {
    width: 32px;
    text-align: right;
    font-size: 10px;
    font-weight: 700;
    color: var(--text-primary);
    flex-shrink: 0;
  }
  .band-hours {
    font-size: 8px;
    color: var(--text-muted);
    padding-left: 82px;
    margin-bottom: 6px;
  }
  .band-row:last-of-type + .band-hours {
    margin-bottom: 0;
  }
  .chart-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    font-size: 12px;
    min-height: 100px;
  }
</style>
