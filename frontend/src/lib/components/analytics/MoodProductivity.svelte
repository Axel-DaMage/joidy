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
  // stacked points stay readable), y = XP earned that day. Pearson r comes
  // precomputed from /analytics/overview.
  type MoodActivity = AnalyticsOverview['mood_activity'];

  let { mood }: { mood?: MoodActivity } = $props();

  const W = 760;
  const H = 300;
  const M = { top: 14, right: 16, bottom: 30, left: 44 };

  // Deterministic jitter — stable across re-renders, keyed on index.
  function jitter(i: number): number {
    const h = Math.sin(i * 127.1 + 311.7) * 43758.5453;
    return (h - Math.floor(h) - 0.5) * 0.36;
  }

  interface Pt {
    date: string;
    mood: number;
    xp: number;
    mx: number; // jittered mood position
  }

  let pts = $derived<Pt[]>(
    (mood?.points ?? []).map((p, i) => ({
      date: p.date,
      mood: p.mood,
      xp: p.xp,
      mx: Math.min(5.45, Math.max(0.55, p.mood + jitter(i))),
    }))
  );

  let x = $derived(scaleLinear().domain([0.4, 5.6]).range([M.left, W - M.right]));
  let y = $derived(
    scaleLinear()
      .domain([0, Math.max(10, (max(pts, (p) => p.xp) ?? 0) * 1.15)])
      .nice()
      .range([H - M.bottom, M.top])
  );
  let yTicks = $derived(y.ticks(5));
  const X_TICKS = [1, 2, 3, 4, 5];
  let dateFmt = $derived(
    new Intl.DateTimeFormat(getLocale(), { day: 'numeric', month: 'short' })
  );

  let r = $derived(mood?.pearson_r ?? null);
  let sampleSize = $derived(mood?.sample_size ?? 0);
  let hasData = $derived(sampleSize >= 3 && pts.length >= 3);

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
  {#snippet icon()}<Smile size={15} />{/snippet}
  {#snippet actions()}
    {#if hasData}
      <span
        class="mp-badge"
        class:pos={(r ?? 0) > 0.15}
        class:neg={(r ?? 0) < -0.15}
        title={$t('goalsAnalytics.mood.correlation', {
          values: { value: r !== null ? r.toFixed(2) : '—' },
        })}
        >{$t('goalsAnalytics.mood.correlation', {
          values: { value: r !== null ? r.toFixed(2) : '—' },
        })}</span
      >
      <span class="mp-samples"
        >{$t('goalsAnalytics.mood.samples', { values: { count: sampleSize } })}</span
      >
    {/if}
  {/snippet}

  {#if !hasData}
    <div class="chart-empty">
      <Smile size={22} style="opacity:0.25" />
      <span>{$t('goalsAnalytics.mood.empty')}</span>
    </div>
  {:else}
    <div class="mp-wrap" bind:this={wrapEl}>
      <svg
        viewBox="0 0 {W} {H}"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={$t('goalsAnalytics.slides.mood')}
      >
        {#each yTicks as tv (tv)}
          <line x1={M.left} x2={W - M.right} y1={y(tv)} y2={y(tv)} class="grid-line" />
          <text x={M.left - 8} y={y(tv) + 3} class="tick" text-anchor="end">{tv}</text>
        {/each}

        {#each X_TICKS as tv (tv)}
          <line x1={x(tv)} x2={x(tv)} y1={H - M.bottom} y2={H - M.bottom + 4} class="axis" />
          <text x={x(tv)} y={H - M.bottom + 16} class="tick" text-anchor="middle">{tv}</text>
        {/each}
        <line x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} class="axis" />
        <text x={(M.left + W - M.right) / 2} y={H - 2} class="tick axis-label" text-anchor="middle"
          >{$t('goalsAnalytics.mood.moodAxis')}</text
        >

        {#each pts as pt (pt.date)}
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <circle
            cx={x(pt.mx)}
            cy={y(pt.xp)}
            r="4"
            class="mp-dot"
            class:hovered={tip?.pt === pt}
            onmouseenter={(e) => onDot(e, pt)}
            onmousemove={(e) => onDot(e, pt)}
            onmouseleave={() => (tip = null)}
          />
        {/each}
      </svg>

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
    </div>
  {/if}
</ChartCard>

<style>
  .mp-wrap {
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
  .axis-label {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .mp-dot {
    fill: color-mix(in srgb, var(--xp) 70%, transparent);
    stroke: var(--xp);
    stroke-width: 1;
    transition: r 0.12s ease;
  }
  .mp-dot.hovered {
    fill: var(--xp);
    r: 5.5;
  }
  .mp-badge {
    font-size: 10px;
    font-weight: 700;
    font-family: var(--font-mono);
    padding: 2px 8px;
    border-radius: 6px;
    border: 1px solid var(--border);
    color: var(--text-muted);
    text-transform: none;
    letter-spacing: 0;
  }
  .mp-badge.pos {
    color: var(--success);
    border-color: color-mix(in srgb, var(--success) 50%, transparent);
    background: color-mix(in srgb, var(--success) 10%, transparent);
  }
  .mp-badge.neg {
    color: var(--error);
    border-color: color-mix(in srgb, var(--error) 50%, transparent);
    background: color-mix(in srgb, var(--error) 10%, transparent);
  }
  .mp-samples {
    font-size: 9px;
    color: var(--text-muted);
    text-transform: none;
    letter-spacing: 0;
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
