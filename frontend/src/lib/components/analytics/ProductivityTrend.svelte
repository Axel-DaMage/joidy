<script lang="ts">
  import {
    scaleTime,
    scaleLinear,
    line,
    area,
    extent,
    max,
    min,
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
  // and an OLS regression trend line (#1499). The SVG is sized from its
  // container (no viewBox scaling) so axis text keeps a constant size and the
  // plot always fills the card.
  type DayActivity = AnalyticsOverview['daily_activity'][number];

  let { activity = [] }: { activity?: DayActivity[] } = $props();

  let W = $state(0);
  let H = $state(0);
  const M = { top: 14, right: 14, bottom: 24, left: 40 };

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
      .range([M.left, Math.max(M.left + 1, W - M.right)])
  );
  // Penalty days (e.g. deleted notes) can be negative — keep them inside the plot.
  let y = $derived(
    scaleLinear()
      .domain([
        Math.min(0, (min(pts, (p) => p.xp) ?? 0) * 1.15),
        Math.max(10, (max(pts, (p) => p.xp) ?? 0) * 1.12),
      ])
      .nice()
      .range([Math.max(M.top + 1, H - M.bottom), M.top])
  );
  let baseY = $derived(y(0));

  let areaPath = $derived(
    area<Pt>()
      .x((p) => x(p.date))
      .y0(baseY)
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

  let regLine = $derived.by(() => {
    if (!reg || pts.length < 2) return null;
    return {
      x1: x(pts[0].date),
      y1: y(reg.predict(0)),
      x2: x(pts[pts.length - 1].date),
      y2: y(reg.predict(pts.length - 1)),
    };
  });

  // Highest day — annotated on the chart so the peak is readable at a glance.
  let peak = $derived(pts.length ? pts.reduce((a, b) => (b.xp > a.xp ? b : a)) : null);

  let xTicks = $derived(
    x.ticks(Math.min(10, Math.max(2, Math.floor((W - M.left - M.right) / 90))))
  );
  let yTicks = $derived(y.ticks(Math.max(3, Math.floor((H - M.top - M.bottom) / 48))));
  let tickFmt = $derived(
    new Intl.DateTimeFormat($locale, { day: 'numeric', month: 'short' })
  );
  const fmtY = (v: number) =>
    Math.abs(v) >= 1000 ? `${+(v / 1000).toFixed(1)}k` : String(v);

  // ── Hover ──────────────────────────────────────────────────────────────────
  let svgEl = $state<SVGSVGElement | null>(null);
  let tip = $state<{ x: number; y: number; pt: Pt } | null>(null);
  const bisectDate = bisector<Pt, Date>((p) => p.date).center;

  function onMove(e: MouseEvent) {
    if (!svgEl || pts.length === 0) return;
    const rect = svgEl.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const mDate = x.invert(Math.max(M.left, Math.min(W - M.right, mx)));
    const pt = pts[Math.min(pts.length - 1, Math.max(0, bisectDate(pts, mDate)))];
    tip = { x: x(pt.date), y: y(pt.xp), pt };
  }
</script>

<ChartCard title={$t('analyticsPage.slides.trend')}>
  {#snippet icon()}<ChartLine size={13} />{/snippet}
  {#snippet actions()}
    <div class="pt-legend">
      <span class="pt-leg"
        ><span class="pt-dot" style="background: var(--xp)"></span>{$t(
          'analyticsPage.trend.dailyXp'
        )}</span
      >
      <span class="pt-leg"
        ><span class="pt-dot" style="background: var(--link)"></span>{$t(
          'analyticsPage.trend.movingAvg'
        )}</span
      >
      <span class="pt-leg"
        ><span class="pt-dash" style="background: var(--text-muted)"></span>{$t(
          'analyticsPage.trend.regression'
        )}</span
      >
    </div>
  {/snippet}

  {#if pts.length === 0}
    <div class="chart-empty">
      <ChartLine size={22} style="opacity:0.25" />
      <span>{$t('analyticsPage.trend.empty')}</span>
    </div>
  {:else}
    <div class="pt-wrap" bind:clientWidth={W} bind:clientHeight={H}>
      {#if W > 0 && H > 0}
        <svg
          bind:this={svgEl}
          width={W}
          height={H}
          role="img"
          aria-label={$t('analyticsPage.slides.trend')}
          onmousemove={onMove}
          onmouseleave={() => (tip = null)}
        >
          {#each yTicks as tv (tv)}
            <line x1={M.left} x2={W - M.right} y1={y(tv)} y2={y(tv)} class="grid-line" />
            <text x={M.left - 8} y={y(tv) + 3} class="tick" text-anchor="end">{fmtY(tv)}</text>
          {/each}

          <path d={areaPath} class="area" />
          <path d={xpPath} class="xp-line" pathLength="1" />
          <path d={maPath} class="ma-line" pathLength="1" />
          {#if regLine}
            <line
              x1={regLine.x1}
              y1={regLine.y1}
              x2={regLine.x2}
              y2={regLine.y2}
              class="reg-line"
            />
          {/if}

          {#if peak && peak.xp > 0}
            <circle cx={x(peak.date)} cy={y(peak.xp)} r="3" class="peak-dot" />
            <text
              x={Math.min(W - M.right - 4, Math.max(M.left + 4, x(peak.date)))}
              y={y(peak.xp) - 9}
              class="peak-label"
              text-anchor={x(peak.date) > W - 80 ? 'end' : 'middle'}
              >{peak.xp.toLocaleString()} · {tickFmt.format(peak.date)}</text
            >
          {/if}

          {#each xTicks as tv (tv.getTime())}
            <line x1={x(tv)} x2={x(tv)} y1={H - M.bottom} y2={H - M.bottom + 4} class="axis" />
            <text x={x(tv)} y={H - M.bottom + 16} class="tick" text-anchor="middle"
              >{tickFmt.format(tv)}</text
            >
          {/each}
          <line x1={M.left} x2={W - M.right} y1={baseY} y2={baseY} class="axis" />

          {#if tip}
            <line x1={x(tip.pt.date)} x2={x(tip.pt.date)} y1={M.top} y2={H - M.bottom} class="crosshair" />
            <circle cx={x(tip.pt.date)} cy={y(tip.pt.xp)} r="3.5" class="hover-dot xp-dot" />
            <circle cx={x(tip.pt.date)} cy={y(ma[tip.pt.i] ?? 0)} r="3" class="hover-dot ma-dot" />
          {/if}
        </svg>

        <ChartTooltip x={tip?.x ?? 0} y={tip?.y ?? 0} visible={!!tip} placeBelow={(tip?.y ?? 0) < 70}>
          {#if tip}
            <span class="tt-title">{tickFmt.format(tip.pt.date)}</span>
            <span class="tt-row"
              ><span class="tt-dot" style="background: var(--xp)"></span>{$t(
                'analyticsPage.trend.dailyXp'
              )}<span class="tt-val">{tip.pt.xp.toLocaleString()}</span></span
            >
            <span class="tt-row"
              ><span class="tt-dot" style="background: var(--link)"></span>{$t(
                'analyticsPage.trend.movingAvg'
              )}<span class="tt-val">{Math.round(ma[tip.pt.i] ?? 0).toLocaleString()}</span></span
            >
          {/if}
        </ChartTooltip>
      {/if}
    </div>
  {/if}
</ChartCard>

<style>
  .pt-wrap {
    position: relative;
    flex: 1;
    min-height: 0;
  }
  svg {
    position: absolute;
    inset: 0;
    display: block;
    cursor: crosshair;
  }
  .grid-line {
    stroke: var(--border);
    stroke-width: 0.5;
    opacity: 0.6;
  }
  .axis {
    stroke: var(--border);
    stroke-width: 1;
  }
  .tick {
    font-size: 10px;
    fill: var(--text-muted);
    font-family: var(--font-mono);
  }
  .area {
    fill: color-mix(in srgb, var(--xp) 10%, transparent);
  }
  .xp-line,
  .ma-line {
    fill: none;
    stroke-linejoin: round;
    stroke-dasharray: 1;
    stroke-dashoffset: 1;
    animation: pt-draw 1.1s ease-out 0.1s forwards;
  }
  .xp-line {
    stroke: var(--xp);
    stroke-width: 1.5;
  }
  .ma-line {
    stroke: var(--link);
    stroke-width: 2;
    animation-delay: 0.25s;
  }
  .reg-line {
    stroke: var(--text-muted);
    stroke-width: 1.25;
    stroke-dasharray: 5 4;
    opacity: 0.8;
  }
  .peak-dot {
    fill: var(--xp);
    stroke: var(--bg);
    stroke-width: 1.5;
  }
  .peak-label {
    font-size: 10px;
    font-family: var(--font-mono);
    fill: var(--text-secondary);
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
    font-size: 10px;
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
    width: 10px;
    height: 2px;
    border-radius: 1px;
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
  }
  @keyframes pt-draw {
    to {
      stroke-dashoffset: 0;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .xp-line,
    .ma-line {
      animation: none;
      stroke-dashoffset: 0;
    }
  }
</style>
