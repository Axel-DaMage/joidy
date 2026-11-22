<script lang="ts">
  import { scaleQuantize } from 'd3';
  import Grid3x3 from 'lucide-svelte/icons/grid-3x3';
  import ChartCard from './ChartCard.svelte';
  import ChartTooltip from './ChartTooltip.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { use24HourClock } from '$lib/stores/settings';
  import { locale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';

  // Weekday × hour density matrix (#1499). `weekday` is Mon=0..Sun=6 per the
  // /analytics/overview contract; hour labels honor the 12/24h preference.
  type Seasonality = AnalyticsOverview['seasonality'];

  let { seasonality }: { seasonality?: Seasonality } = $props();

  const W = 760;
  const H = 230;
  const M = { top: 8, right: 10, bottom: 24, left: 44 };
  const COLS = 24;
  const ROWS = 7;

  let cells = $derived(seasonality?.cells ?? []);
  let max = $derived(Math.max(1, seasonality?.max ?? 0));
  let lookup = $derived(new Map(cells.map((c) => [`${c.weekday}-${c.hour}`, c.count])));
  let levelScale = $derived(scaleQuantize<number>().domain([0, max]).range([1, 2, 3, 4, 5]));

  const cellW = (W - M.left - M.right) / COLS;
  const cellH = (H - M.top - M.bottom) / ROWS;
  const HOUR_TICKS = [0, 3, 6, 9, 12, 15, 18, 21];

  function countAt(weekday: number, hour: number): number {
    return lookup.get(`${weekday}-${hour}`) ?? 0;
  }
  function levelAt(weekday: number, hour: number): number {
    const c = countAt(weekday, hour);
    return c <= 0 ? 0 : levelScale(c);
  }

  const weekdayFmt = $derived(new Intl.DateTimeFormat($locale, { weekday: 'short' }));
  const weekdayLongFmt = $derived(new Intl.DateTimeFormat($locale, { weekday: 'long' }));
  // 2024-01-01 was a Monday — index 0..6 maps to Mon..Sun in any locale.
  const weekdayLabel = (i: number) => weekdayFmt.format(new Date(2024, 0, 1 + i));
  const weekdayLong = (i: number) => weekdayLongFmt.format(new Date(2024, 0, 1 + i));

  function formatHourLabel(hour: number): string {
    const h = ((hour % 24) + 24) % 24;
    if ($use24HourClock) return `${String(h).padStart(2, '0')}:00`;
    return new Date(2020, 0, 1, h, 0, 0, 0).toLocaleTimeString($locale, {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  }

  // Peak insight — densest cell in the matrix.
  let peak = $derived.by(() => {
    if (cells.length === 0) return null;
    return cells.reduce((a, b) => (b.count > a.count ? b : a), cells[0]);
  });

  // ── Hover ──────────────────────────────────────────────────────────────────
  let wrapEl = $state<HTMLDivElement | null>(null);
  let tip = $state<{ x: number; y: number; weekday: number; hour: number; count: number } | null>(
    null
  );

  function onCell(e: MouseEvent, weekday: number, hour: number) {
    if (!wrapEl) return;
    const r = wrapEl.getBoundingClientRect();
    tip = {
      x: e.clientX - r.left,
      y: e.clientY - r.top,
      weekday,
      hour,
      count: countAt(weekday, hour),
    };
  }
</script>

<ChartCard title={$t('goalsAnalytics.slides.seasonality')}>
  {#snippet icon()}<Grid3x3 size={15} />{/snippet}
  {#snippet actions()}
    {#if peak && peak.count > 0}
      <span class="sm-peak"
        >{$t('goalsAnalytics.seasonality.peak', {
          values: { day: weekdayLong(peak.weekday), hour: formatHourLabel(peak.hour) },
        })}</span
      >
    {/if}
  {/snippet}

  {#if cells.length === 0}
    <div class="chart-empty">
      <Grid3x3 size={22} style="opacity:0.25" />
      <span>{$t('goalsAnalytics.seasonality.empty')}</span>
    </div>
  {:else}
    <div class="sm-wrap" bind:this={wrapEl}>
      <svg
        viewBox="0 0 {W} {H}"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={$t('goalsAnalytics.slides.seasonality')}
      >
        {#each Array.from({ length: ROWS }, (_, wd) => wd) as wd (wd)}
          <text
            x={M.left - 8}
            y={M.top + wd * cellH + cellH / 2 + 3}
            class="tick"
            text-anchor="end">{weekdayLabel(wd)}</text
          >
          {#each Array.from({ length: COLS }, (_, h) => h) as h (h)}
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <rect
              x={M.left + h * cellW + 1}
              y={M.top + wd * cellH + 1}
              width={cellW - 2}
              height={cellH - 2}
              rx="3"
              class="sm-cell c{levelAt(wd, h)}"
              onmouseenter={(e) => onCell(e, wd, h)}
              onmousemove={(e) => onCell(e, wd, h)}
              onmouseleave={() => (tip = null)}
            />
          {/each}
        {/each}
        {#each HOUR_TICKS as h (h)}
          <text
            x={M.left + h * cellW + cellW / 2}
            y={H - 8}
            class="tick"
            text-anchor="middle">{formatHourLabel(h)}</text
          >
        {/each}
      </svg>

      <ChartTooltip
        x={tip?.x ?? 0}
        y={tip?.y ?? 0}
        visible={!!tip}
        placeBelow={(tip?.y ?? 0) < 60}
      >
        {#if tip}
          <span class="tt-title">{weekdayLong(tip.weekday)} · {formatHourLabel(tip.hour)}</span>
          <span class="tt-row"
            >{$t('goalsAnalytics.heatmap.events', { values: { count: tip.count } })}</span
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
  }
  svg {
    width: 100%;
    height: 100%;
    min-height: 180px;
    display: block;
  }
  .tick {
    font-size: 9px;
    fill: var(--text-muted);
    font-family: var(--font-mono);
  }
  .sm-cell {
    stroke: none;
  }
  .sm-cell.c0 {
    fill: color-mix(in srgb, var(--text-primary) 6%, transparent);
  }
  .sm-cell.c1 {
    fill: color-mix(in srgb, var(--xp) 22%, transparent);
  }
  .sm-cell.c2 {
    fill: color-mix(in srgb, var(--xp) 40%, transparent);
  }
  .sm-cell.c3 {
    fill: color-mix(in srgb, var(--xp) 58%, transparent);
  }
  .sm-cell.c4 {
    fill: color-mix(in srgb, var(--xp) 78%, transparent);
  }
  .sm-cell.c5 {
    fill: var(--xp);
  }
  .sm-peak {
    font-size: 9px;
    color: var(--xp);
    text-transform: none;
    letter-spacing: 0;
    font-weight: 700;
  }
  .chart-empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: var(--text-muted);
    font-size: 12px;
    text-align: center;
    min-height: 160px;
  }
</style>
