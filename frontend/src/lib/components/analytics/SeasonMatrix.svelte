<script lang="ts">
  import { scaleQuantize } from 'd3';
  import Grid3x3 from 'lucide-svelte/icons/grid-3x3';
  import ChartCard from './ChartCard.svelte';
  import ChartTooltip from './ChartTooltip.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { cellValue } from '$lib/utils/insights';
  import { locale } from '$lib/stores/locale';
  import { use24HourClock } from '$lib/stores/settings';
  import { t } from 'svelte-i18n';

  // Weekday × hour matrix (#1499): the canonical seasonality view. Every
  // cell is the XP earned at that weekday/hour over the window; colour is a
  // quantile bucket so a single huge hour cannot wash out the rest.
  type Seasonality = AnalyticsOverview['seasonality'];

  let { seasonality }: { seasonality?: Seasonality } = $props();

  const HOURS = Array.from({ length: 24 }, (_, h) => h);
  const DAYS = [0, 1, 2, 3, 4, 5, 6];

  let grid = $derived.by(() => {
    const m = DAYS.map(() => new Array<number>(24).fill(0));
    for (const c of seasonality?.cells ?? []) m[c.weekday][c.hour] += cellValue(c);
    return m;
  });
  let max = $derived(Math.max(0, ...grid.flat()));
  let scale = $derived(scaleQuantize<number>().domain([0, Math.max(1, max)]).range([1, 2, 3, 4, 5]));
  const level = (v: number) => (v <= 0 ? 0 : scale(v));
  let peak = $derived.by(() => {
    let best = { d: 0, h: 0, v: -1 };
    grid.forEach((row, d) => row.forEach((v, h) => v > best.v && (best = { d, h, v })));
    return max > 0 ? best : null;
  });

  let dayNames = $derived(
    DAYS.map((i) =>
      new Intl.DateTimeFormat($locale, { weekday: 'short' })
        .format(new Date(2024, 0, 1 + i))
        .replace('.', '')
    )
  );
  const fmtHour = (h: number) =>
    $use24HourClock
      ? `${String(h).padStart(2, '0')}:00`
      : h === 0
        ? '12am'
        : h < 12
          ? `${h}am`
          : h === 12
            ? '12pm'
            : `${h - 12}pm`;

  let wrapEl = $state<HTMLDivElement | null>(null);
  let tip = $state<{ x: number; y: number; d: number; h: number; v: number } | null>(null);
  function onCell(e: MouseEvent, d: number, h: number) {
    if (!wrapEl) return;
    const r = wrapEl.getBoundingClientRect();
    const c = (e.currentTarget as HTMLElement).getBoundingClientRect();
    tip = { x: c.left - r.left + c.width / 2, y: c.top - r.top, d, h, v: grid[d][h] };
  }
</script>

<ChartCard title={$t('analyticsPage.matrix.title')}>
  {#snippet icon()}<Grid3x3 size={13} />{/snippet}
  {#snippet actions()}
    {#if peak}
      <span class="sm-peak mono"
        >{$t('analyticsPage.matrix.peak', {
          values: { day: dayNames[peak.d], hour: fmtHour(peak.h) },
        })}</span
      >
    {/if}
  {/snippet}

  {#if max === 0}
    <div class="chart-empty"><span>{$t('analyticsPage.seasonality.empty')}</span></div>
  {:else}
    <div class="sm-wrap" bind:this={wrapEl}>
      <div class="sm-grid">
        <span></span>
        {#each HOURS as h (h)}
          <span class="sm-hour mono">{h % 3 === 0 ? String(h).padStart(2, '0') : ''}</span>
        {/each}
        {#each DAYS as d (d)}
          <span class="sm-day mono">{dayNames[d]}</span>
          {#each HOURS as h (h)}
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div
              class="sm-cell lv{level(grid[d][h])}"
              class:peak={peak && peak.d === d && peak.h === h}
              style:--delay="{(h + d * 2) * 9}ms"
              onmouseenter={(e) => onCell(e, d, h)}
              onmouseleave={() => (tip = null)}
            ></div>
          {/each}
        {/each}
      </div>
      <div class="sm-legend mono">
        <span>{$t('analyticsPage.heatmap.less')}</span>
        {#each [0, 1, 2, 3, 4, 5] as lv (lv)}<span class="sm-lg lv{lv}"></span>{/each}
        <span>{$t('analyticsPage.heatmap.more')}</span>
      </div>

      <ChartTooltip x={tip?.x ?? 0} y={tip?.y ?? 0} visible={!!tip} placeBelow={(tip?.y ?? 0) < 70}>
        {#if tip}
          <span class="tt-title">{dayNames[tip.d]} · {fmtHour(tip.h)}</span>
          <span class="tt-row"
            ><span class="tt-dot" style="background: var(--xp)"></span>{$t(
              'analyticsPage.heatmap.xpOn',
              { values: { xp: tip.v.toLocaleString() } }
            )}</span
          >
        {/if}
      </ChartTooltip>
    </div>
  {/if}
</ChartCard>

<style>
  .sm-wrap {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s2);
  }
  .sm-grid {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: 30px repeat(24, minmax(0, 1fr));
    grid-template-rows: 14px repeat(7, minmax(0, 1fr));
    gap: 3px;
  }
  .sm-hour,
  .sm-day {
    font-size: 10px;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    text-transform: capitalize;
  }
  .sm-hour {
    justify-content: flex-start;
    overflow: visible;
    white-space: nowrap;
  }
  .sm-cell {
    border-radius: var(--r-sm);
    transition: outline-color 0.12s;
    outline: 1px solid transparent;
    animation: sm-pop 0.5s cubic-bezier(0.2, 0.7, 0.2, 1) both;
    animation-delay: var(--delay);
  }
  .sm-cell:hover {
    outline-color: var(--text-secondary);
  }
  .sm-cell.peak {
    outline: 1px solid var(--text-primary);
  }
  .lv0 {
    background: color-mix(in srgb, var(--text-primary) 5%, transparent);
  }
  .lv1 {
    background: color-mix(in srgb, var(--xp) 24%, transparent);
  }
  .lv2 {
    background: color-mix(in srgb, var(--xp) 42%, transparent);
  }
  .lv3 {
    background: color-mix(in srgb, var(--xp) 62%, transparent);
  }
  .lv4 {
    background: color-mix(in srgb, var(--xp) 82%, transparent);
  }
  .lv5 {
    background: var(--xp);
  }
  .sm-legend {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 3px;
    font-size: 10px;
    color: var(--text-muted);
    flex-shrink: 0;
  }
  .sm-lg {
    width: 12px;
    height: 12px;
    border-radius: var(--r-sm);
  }
  .sm-peak {
    font-size: 10px;
    font-weight: 700;
    text-transform: none;
    letter-spacing: 0;
    color: var(--text-secondary);
    white-space: nowrap;
  }
  .chart-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    font-size: 12px;
  }
  @keyframes sm-pop {
    from {
      opacity: 0;
      transform: scale(0.6);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .sm-cell {
      animation: none;
    }
  }
</style>
