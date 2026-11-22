<script lang="ts">
  import { scaleBand, scaleLinear } from 'd3';
  import ChartColumn from 'lucide-svelte/icons/chart-column';
  import ChartCard from './ChartCard.svelte';
  import ChartTooltip from './ChartTooltip.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { xpByWeekday } from '$lib/utils/insights';
  import { locale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';

  // Compact weekday profile (#1499): average XP per day of week — the
  // "which days am I productive" complement to the heatmap.
  type DayRow = AnalyticsOverview['daily_activity'][number];

  let { activity }: { activity?: DayRow[] } = $props();

  const W = 320;
  const H = 120;
  const M = { top: 8, right: 4, bottom: 20, left: 4 };

  let avgs = $derived.by(() => {
    const rows = activity ?? [];
    const sums = xpByWeekday(rows);
    const counts = Array(7).fill(0) as number[];
    for (const d of rows) counts[(new Date(d.date + 'T12:00').getDay() + 6) % 7]++;
    return sums.map((s, i) => (counts[i] > 0 ? Math.round(s / counts[i]) : 0));
  });
  let max = $derived(Math.max(1, ...avgs));
  let best = $derived(avgs.indexOf(max));

  let x = $derived(
    scaleBand()
      .domain(avgs.map((_, i) => String(i)))
      .range([M.left, W - M.right])
      .paddingInner(0.28)
  );
  let y = $derived(
    scaleLinear()
      .domain([0, max])
      .range([H - M.bottom, M.top])
      .nice()
  );
  let dayNames = $derived(
    Array.from({ length: 7 }, (_, i) =>
      new Intl.DateTimeFormat($locale, { weekday: 'short' })
        .format(new Date(2024, 0, 1 + i))
        .replace('.', '')
    )
  );

  let wrapEl = $state<HTMLDivElement | null>(null);
  let tip = $state<{ x: number; y: number; day: string; xp: number } | null>(null);

  function onBar(e: MouseEvent, i: number) {
    if (!wrapEl) return;
    const r = wrapEl.getBoundingClientRect();
    tip = { x: e.clientX - r.left, y: e.clientY - r.top, day: dayNames[i], xp: avgs[i] };
  }
</script>

<ChartCard title={$t('goalsAnalytics.weekday.title')}>
  {#snippet icon()}<ChartColumn size={15} />{/snippet}

  {#if max <= 1 && avgs.every((v) => v === 0)}
    <div class="chart-empty"><span>{$t('goalsAnalytics.weekday.empty')}</span></div>
  {:else}
    <div class="wd-wrap" bind:this={wrapEl}>
      <svg
        viewBox="0 0 {W} {H}"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={$t('goalsAnalytics.weekday.title')}
      >
        {#each avgs as v, i (i)}
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <rect
            x={x(String(i))}
            y={y(v)}
            width={x.bandwidth()}
            height={Math.max(2, H - M.bottom - y(v))}
            rx="4"
            class="wd-bar"
            class:peak={i === best}
            onmouseenter={(e) => onBar(e, i)}
            onmousemove={(e) => onBar(e, i)}
            onmouseleave={() => (tip = null)}
          />
          <text x={(x(String(i)) ?? 0) + x.bandwidth() / 2} y={H - 6} class="wd-label" text-anchor="middle"
            >{dayNames[i]}</text
          >
        {/each}
      </svg>

      <ChartTooltip x={tip?.x ?? 0} y={tip?.y ?? 0} visible={!!tip}>
        {#if tip}
          <span class="tt-title">{tip.day}</span>
          <span class="tt-row">{$t('goalsAnalytics.weekday.avg', { values: { xp: tip.xp } })}</span>
        {/if}
      </ChartTooltip>
    </div>
  {/if}
</ChartCard>

<style>
  .wd-wrap {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    align-items: stretch;
  }
  svg {
    width: 100%;
    height: 100%;
  }
  .wd-bar {
    fill: color-mix(in srgb, var(--xp) 45%, transparent);
    transition: fill 0.2s;
    cursor: default;
  }
  .wd-bar:hover {
    fill: color-mix(in srgb, var(--xp) 70%, transparent);
  }
  .wd-bar.peak {
    fill: var(--xp);
  }
  .wd-label {
    fill: var(--text-muted);
    font-size: 9px;
    font-family: var(--font-mono);
    text-transform: capitalize;
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
