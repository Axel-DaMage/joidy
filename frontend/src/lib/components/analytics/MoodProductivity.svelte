<script lang="ts">
  import { scaleLinear, max } from 'd3';
  import Smile from 'lucide-svelte/icons/smile';
  import ChartCard from './ChartCard.svelte';
  import ChartTooltip from './ChartTooltip.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { parseLocalDate } from '$lib/utils/date';
  import { getLocale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';

  // Mood × productivity scatter (#1499): x = mood score (1–5, jittered so
  // stacked points stay readable), y = XP earned that day. The tick on each
  // mood column is the mean XP of that mood. Pearson r comes precomputed from
  // /analytics/overview. With no mood entries a ghost preview of the chart is
  // shown with a pointer to where mood is logged.
  type MoodActivity = AnalyticsOverview['mood_activity'];

  let { mood }: { mood?: MoodActivity } = $props();

  let W = $state(0);
  let H = $state(0);
  const M = { top: 14, right: 16, bottom: 30, left: 40 };

  // Deterministic jitter — stable across re-renders, keyed on index.
  function jitter(i: number): number {
    const h = Math.sin(i * 127.1 + 311.7) * 43758.5453;
    return (h - Math.floor(h) - 0.5) * 0.36;
  }

  interface Pt {
    date: string;
    mood: number;
    xp: number;
    mx: number;
  }

  let pts = $derived<Pt[]>(
    (mood?.points ?? []).map((p, i) => ({
      date: p.date,
      mood: p.mood,
      xp: p.xp,
      mx: Math.min(5.45, Math.max(0.55, p.mood + jitter(i))),
    }))
  );

  let x = $derived(scaleLinear().domain([0.4, 5.6]).range([M.left, Math.max(M.left + 1, W - M.right)]));
  let y = $derived(
    scaleLinear()
      .domain([0, Math.max(10, (max(pts, (p) => p.xp) ?? 0) * 1.15)])
      .nice()
      .range([Math.max(M.top + 1, H - M.bottom), M.top])
  );
  let yTicks = $derived(y.ticks(Math.max(3, Math.floor((H - M.top - M.bottom) / 48))));
  const X_TICKS = [1, 2, 3, 4, 5];
  const fmtY = (v: number) => (v >= 1000 ? `${+(v / 1000).toFixed(1)}k` : String(v));
  let dateFmt = $derived(
    new Intl.DateTimeFormat(getLocale(), { day: 'numeric', month: 'short' })
  );

  let means = $derived(
    X_TICKS.map((m) => {
      const xs = pts.filter((p) => p.mood === m);
      return xs.length ? { m, v: xs.reduce((a, p) => a + p.xp, 0) / xs.length } : null;
    }).filter((d): d is { m: number; v: number } => d !== null)
  );

  let r = $derived(mood?.pearson_r ?? null);
  let sampleSize = $derived(mood?.sample_size ?? 0);
  let hasData = $derived(sampleSize >= 3 && pts.length >= 3);

  // Ghost dataset for the empty state (purely decorative).
  const GHOST = [
    [1, 0.18], [1, 0.1], [2, 0.3], [2, 0.22], [2, 0.38], [3, 0.42], [3, 0.5], [3, 0.35],
    [3, 0.6], [4, 0.58], [4, 0.7], [4, 0.52], [5, 0.78], [5, 0.66], [5, 0.85],
  ] as const;

  // ── Hover ──────────────────────────────────────────────────────────────────
  let wrapEl = $state<HTMLDivElement | null>(null);
  let tip = $state<{ x: number; y: number; pt: Pt } | null>(null);

  function onDot(e: MouseEvent, pt: Pt) {
    if (!wrapEl) return;
    const rect = wrapEl.getBoundingClientRect();
    tip = { x: e.clientX - rect.left, y: e.clientY - rect.top, pt };
  }
</script>

<ChartCard title={$t('goalsAnalytics.slides.mood')}>
  {#snippet icon()}<Smile size={13} />{/snippet}
  {#snippet actions()}
    {#if hasData}
      <span class="mp-badge mono"
        >{$t('goalsAnalytics.mood.correlation', {
          values: { value: r !== null ? r.toFixed(2) : '—' },
        })}</span
      >
      <span class="mp-samples"
        >{$t('goalsAnalytics.mood.samples', { values: { count: sampleSize } })}</span
      >
    {/if}
  {/snippet}

  <div class="mp-wrap" bind:this={wrapEl} bind:clientWidth={W} bind:clientHeight={H}>
    {#if W > 0 && H > 0}
      <svg width={W} height={H} role="img" aria-label={$t('goalsAnalytics.slides.mood')}>
        {#each yTicks as tv (tv)}
          <line x1={M.left} x2={W - M.right} y1={y(tv)} y2={y(tv)} class="grid-line" />
          {#if hasData}
            <text x={M.left - 8} y={y(tv) + 3} class="tick" text-anchor="end">{fmtY(tv)}</text>
          {/if}
        {/each}

        {#each X_TICKS as tv (tv)}
          <line x1={x(tv)} x2={x(tv)} y1={H - M.bottom} y2={H - M.bottom + 4} class="axis" />
          <text x={x(tv)} y={H - M.bottom + 16} class="tick" text-anchor="middle">{tv}</text>
        {/each}
        <line x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} class="axis" />
        <text x={(M.left + W - M.right) / 2} y={H - 2} class="tick axis-label" text-anchor="middle"
          >{$t('goalsAnalytics.mood.moodAxis')}</text
        >

        {#if hasData}
          {#each means as d (d.m)}
            <line
              x1={x(d.m) - 22}
              x2={x(d.m) + 22}
              y1={y(d.v)}
              y2={y(d.v)}
              class="mp-mean"
            />
          {/each}
          {#each pts as pt, i (pt.date)}
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <circle
              cx={x(pt.mx)}
              cy={y(pt.xp)}
              r="4"
              class="mp-dot"
              class:hovered={tip?.pt === pt}
              style:--i={i}
              onmouseenter={(e) => onDot(e, pt)}
              onmousemove={(e) => onDot(e, pt)}
              onmouseleave={() => (tip = null)}
            />
          {/each}
        {:else}
          <g class="mp-ghost" aria-hidden="true">
            <line
              x1={x(0.8)}
              y1={y(y.domain()[1] * 0.12)}
              x2={x(5.2)}
              y2={y(y.domain()[1] * 0.8)}
              class="mp-ghost-trend"
            />
            {#each GHOST as [m, v], i (i)}
              <circle
                cx={x(m + ((i % 3) - 1) * 0.14)}
                cy={y(y.domain()[1] * v)}
                r="4"
                class="mp-ghost-dot"
              />
            {/each}
          </g>
        {/if}
      </svg>

      {#if !hasData}
        <div class="mp-empty">
          <Smile size={20} />
          <span class="mp-empty-title">{$t('goalsAnalytics.mood.emptyTitle')}</span>
          <span class="mp-empty-body">{$t('goalsAnalytics.mood.empty')}</span>
          <a class="mp-cta" href="/">{$t('goalsAnalytics.mood.cta')}</a>
        </div>
      {/if}

      <ChartTooltip
        x={tip?.x ?? 0}
        y={tip?.y ?? 0}
        visible={!!tip}
        placeBelow={(tip?.y ?? 0) < 70}
      >
        {#if tip}
          <span class="tt-title">{dateFmt.format(parseLocalDate(tip.pt.date))}</span>
          <span class="tt-row"
            >{$t('goalsAnalytics.mood.moodAxis')}<span class="tt-val">{tip.pt.mood}</span></span
          >
          <span class="tt-row"
            >{$t('goalsAnalytics.mood.xpAxis')}<span class="tt-val">{tip.pt.xp}</span></span
          >
        {/if}
      </ChartTooltip>
    {/if}
  </div>
</ChartCard>

<style>
  .mp-wrap {
    position: relative;
    flex: 1;
    min-height: 0;
  }
  svg {
    position: absolute;
    inset: 0;
    display: block;
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
    font-size: 9px;
    fill: var(--text-muted);
    font-family: var(--font-mono);
  }
  .axis-label {
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .mp-dot {
    fill: color-mix(in srgb, var(--xp) 60%, transparent);
    stroke: var(--xp);
    stroke-width: 1;
    transition: r 0.15s;
    animation: mp-fade 0.4s ease both;
    animation-delay: calc(var(--i) * 12ms);
  }
  .mp-dot.hovered {
    r: 6;
    fill: var(--xp);
  }
  .mp-mean {
    stroke: var(--text-secondary);
    stroke-width: 1.5;
    stroke-linecap: round;
  }
  .mp-ghost {
    opacity: 0.4;
  }
  .mp-ghost-dot {
    fill: none;
    stroke: var(--text-muted);
    stroke-width: 1;
    stroke-dasharray: 2 2;
  }
  .mp-ghost-trend {
    stroke: var(--text-muted);
    stroke-width: 1;
    stroke-dasharray: 5 4;
  }
  .mp-badge {
    font-size: 9px;
    font-weight: 700;
    color: var(--text-secondary);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 1px 6px;
    text-transform: none;
    letter-spacing: 0;
  }
  .mp-samples {
    font-size: 9px;
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
    color: var(--text-muted);
  }
  .mp-empty {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -52%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    max-width: 320px;
    text-align: center;
    padding: var(--s4) var(--s5);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    animation: mp-fade 0.5s ease 0.15s both;
  }
  .mp-empty-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
  }
  .mp-empty-body {
    font-size: 11px;
    line-height: 1.5;
  }
  .mp-cta {
    margin-top: var(--s2);
    padding: 5px 14px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    text-decoration: none;
    transition: all 0.15s;
  }
  .mp-cta:hover {
    color: var(--xp);
    border-color: var(--xp);
  }
  @keyframes mp-fade {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .mp-dot,
    .mp-empty {
      animation: none;
    }
  }
</style>
