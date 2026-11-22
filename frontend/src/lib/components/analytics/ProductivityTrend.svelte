<script lang="ts">
  import {
    scaleTime,
    scaleLinear,
    line,
    area,
    extent,
    max,
    bisector,
    curveMonotoneX,
  } from 'd3';
  import ChartLine from 'lucide-svelte/icons/chart-line';
  import ChartCard from './ChartCard.svelte';
  import ChartTooltip from './ChartTooltip.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { movingAverage, linearRegression } from '$lib/utils/stats';
  import { parseLocalDate } from '$lib/utils/date';
  import { locale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';

  // Daily XP line+area chart with a client-side 7-day moving-average overlay
  // and an OLS regression trend line (#1499).
  type DayActivity = AnalyticsOverview['daily_activity'][number];

  let { activity = [] }: { activity?: DayActivity[] } = $props();

  const W = 760;
  const H = 300;
  const M = { top: 14, right: 16, bottom: 26, left: 44 };

  interface Pt {
    i: number;
    date: Date;
    xp: number;
  }

  let pts = $derived<Pt[]>(
    activity.map((d, i) => ({ i, date: parseLocalDate(d.date), xp: d.xp }))
  );
  let ma = $derived(movingAverage(activity.map((d) => d.xp), 7));
  let reg = $derived(linearRegression(activity.map((d) => d.xp)));

  let x = $derived(
    scaleTime()
      .domain((extent(pts, (p) => p.date) as [Date, Date]) ?? [new Date(), new Date()])
      .range([M.left, W - M.right])
  );
  let y = $derived(
    scaleLinear()
      .domain([0, Math.max(10, (max(pts, (p) => p.xp) ?? 0) * 1.15)])
      .nice()
      .range([H - M.bottom, M.top])
  );

  let areaPath = $derived(
    area<Pt>()
      .x((p) => x(p.date))
      .y0(H - M.bottom)
      .y1((p) => y(p.xp))
      .curve(curveMonotoneX)(pts) ?? ''
  );
  let xpPath = $derived(
    line<Pt>()
      .x((p) => x(p.date))
      .y((p) => y(p.xp))
      .curve(curveMonotoneX)(pts) ?? ''
  );
  let maPath = $derived(
    line<Pt>()
      .x((p) => x(p.date))
      .y((p) => y(ma[p.i] ?? 0))
      .curve(curveMonotoneX)(pts) ?? ''
  );

  // Regression line drawn between the first and last point of the series.
  let regLine = $derived.by(() => {
    if (!reg || pts.length < 2) return null;
    return {
      x1: x(pts[0].date),
      y1: y(reg.predict(0)),
      x2: x(pts[pts.length - 1].date),
      y2: y(reg.predict(pts.length - 1)),
    };
  });

  let xTicks = $derived(x.ticks(Math.min(8, Math.max(2, Math.floor(pts.length / 20)))));
  let yTicks = $derived(y.ticks(5));
  let tickFmt = $derived(new Intl.DateTimeFormat($locale, { day: 'numeric', month: 'short' }));

  // ── Hover ──────────────────────────────────────────────────────────────────
  let svgEl = $state<SVGSVGElement | null>(null);
  let tip = $state<{ x: number; y: number; pt: Pt } | null>(null);
  const bisectDate = bisector<Pt, Date>((p) => p.date).center;

  function onMove(e: MouseEvent) {
    if (!svgEl || pts.length === 0) return;
    const rect = svgEl.getBoundingClientRect();
    const mx = ((e.clientX - rect.left) / rect.width) * W;
    const mDate = x.invert(Math.max(M.left, Math.min(W - M.right, mx)));
    const pt = pts[Math.min(pts.length - 1, Math.max(0, bisectDate(pts, mDate)))];
    // Convert viewBox coords back to CSS px for the HTML tooltip.
    const px = (x(pt.date) / W) * rect.width;
    const py = (y(pt.xp) / H) * rect.height;
    tip = { x: px, y: py, pt };
  }
</script>

<ChartCard title={$t('goalsAnalytics.slides.trend')}>
  {#snippet icon()}<ChartLine size={15} />{/snippet}
  {#snippet actions()}
    <div class="pt-legend">
      <span class="pt-leg"><span class="pt-dot" style="background: var(--xp)"></span>{$t(
          'goalsAnalytics.trend.dailyXp'
        )}</span>
      <span class="pt-leg"><span class="pt-dot" style="background: var(--link)"></span>{$t(
          'goalsAnalytics.trend.movingAvg'
        )}</span>
      <span class="pt-leg"><span class="pt-dot pt-dash" style="background: var(--text-muted)"></span
        >{$t('goalsAnalytics.trend.regression')}</span>
    </div>
  {/snippet}

  {#if pts.length === 0}
    <div class="chart-empty">
      <ChartLine size={22} style="opacity:0.25" />
      <span>{$t('goalsAnalytics.trend.empty')}</span>
    </div>
  {:else}
    <div class="pt-wrap">
      <svg
        bind:this={svgEl}
        viewBox="0 0 {W} {H}"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={$t('goalsAnalytics.slides.trend')}
        onmousemove={onMove}
        onmouseleave={() => (tip = null)}
      >
        <!-- grid -->
        {#each yTicks as tv (tv)}
          <line
            x1={M.left}
            x2={W - M.right}
            y1={y(tv)}
            y2={y(tv)}
            class="grid-line"
          />
          <text x={M.left - 8} y={y(tv) + 3} class="tick" text-anchor="end">{tv}</text>
        {/each}

        <!-- area + xp line -->
        <path d={areaPath} class="area" />
        <path d={xpPath} class="xp-line" />
        <path d={maPath} class="ma-line" />
        {#if regLine}
          <line
            x1={regLine.x1}
            y1={regLine.y1}
            x2={regLine.x2}
            y2={regLine.y2}
            class="reg-line"
          />
        {/if}

        <!-- x axis -->
        {#each xTicks as tv (tv.getTime())}
          <line x1={x(tv)} x2={x(tv)} y1={H - M.bottom} y2={H - M.bottom + 4} class="axis" />
          <text x={x(tv)} y={H - M.bottom + 16} class="tick" text-anchor="middle"
            >{tickFmt.format(tv)}</text
          >
        {/each}
        <line x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} class="axis" />

        <!-- hover crosshair -->
        {#if tip}
          <line
            x1={x(tip.pt.date)}
            x2={x(tip.pt.date)}
            y1={M.top}
            y2={H - M.bottom}
            class="crosshair"
          />
          <circle cx={x(tip.pt.date)} cy={y(tip.pt.xp)} r="3.5" class="hover-dot xp-dot" />
          <circle cx={x(tip.pt.date)} cy={y(ma[tip.pt.i] ?? 0)} r="3" class="hover-dot ma-dot" />
        {/if}
      </svg>

      <ChartTooltip x={tip?.x ?? 0} y={tip?.y ?? 0} visible={!!tip} placeBelow={(tip?.y ?? 0) < 70}>
        {#if tip}
          <span class="tt-title">{tickFmt.format(tip.pt.date)}</span>
          <span class="tt-row"
            ><span class="tt-dot" style="background: var(--xp)"></span>{$t(
              'goalsAnalytics.trend.dailyXp'
            )}<span class="tt-val">{tip.pt.xp}</span></span
          >
          <span class="tt-row"
            ><span class="tt-dot" style="background: var(--link)"></span>{$t(
              'goalsAnalytics.trend.movingAvg'
            )}<span class="tt-val">{Math.round(ma[tip.pt.i] ?? 0)}</span></span
          >
        {/if}
      </ChartTooltip>
    </div>
  {/if}
</ChartCard>

<style>
  .pt-wrap {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
  }
  svg {
    width: 100%;
    height: 100%;
    min-height: 220px;
    display: block;
    cursor: crosshair;
  }
  .grid-line {
    stroke: var(--border);
    stroke-width: 0.5;
    opacity: 0.5;
  }
  .axis {
    stroke: var(--border);
    stroke-width: 1;
  }
  .tick {
    font-size: 9px;
    fill: var(--text-muted);
    font-family: var(--font-mono);
  }
  .area {
    fill: color-mix(in srgb, var(--xp) 14%, transparent);
  }
  .xp-line {
    fill: none;
    stroke: var(--xp);
    stroke-width: 1.5;
  }
  .ma-line {
    fill: none;
    stroke: var(--link);
    stroke-width: 2;
  }
  .reg-line {
    stroke: var(--text-muted);
    stroke-width: 1.25;
    stroke-dasharray: 5 4;
    opacity: 0.8;
  }
  .crosshair {
    stroke: var(--text-muted);
    stroke-width: 0.5;
    opacity: 0.6;
  }
  .hover-dot {
    stroke: var(--bg);
    stroke-width: 1.5;
  }
  .xp-dot {
    fill: var(--xp);
  }
  .ma-dot {
    fill: var(--link);
  }
  .pt-legend {
    display: flex;
    gap: var(--s3);
    flex-wrap: wrap;
  }
  .pt-leg {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 9px;
    color: var(--text-muted);
    text-transform: none;
    letter-spacing: 0;
    font-weight: 400;
  }
  .pt-dot {
    width: 8px;
    height: 8px;
    border-radius: 2px;
  }
  .pt-dash {
    height: 2px;
    border-radius: 1px;
    margin: 3px 0;
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
    min-height: 180px;
  }
</style>
