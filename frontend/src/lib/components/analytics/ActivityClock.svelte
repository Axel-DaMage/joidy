<script lang="ts">
  import { scaleQuantize } from 'd3';
  import Clock from 'lucide-svelte/icons/clock';
  import ChartCard from './ChartCard.svelte';
  import ChartTooltip from './ChartTooltip.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { hoursFromCells } from '$lib/utils/insights';
  import { use24HourClock } from '$lib/stores/settings';
  import { t } from 'svelte-i18n';

  // Radial 24h activity clock (#1499): one bar per hour around a clock face,
  // length = events, color = intensity quintile. Scope toggle splits the
  // seasonality cells into weekdays vs weekend.
  type Seasonality = AnalyticsOverview['seasonality'];

  let { seasonality }: { seasonality?: Seasonality } = $props();

  const SIZE = 380;
  const C = SIZE / 2;
  const R0 = 64;
  const MAX_LEN = 92;
  const LABEL_R = 174;
  const TICK_HOURS = [0, 3, 6, 9, 12, 15, 18, 21];

  type Scope = 'all' | 'weekday' | 'weekend';
  let scope = $state<Scope>('all');
  const SCOPES: Scope[] = ['all', 'weekday', 'weekend'];

  let cells = $derived(seasonality?.cells ?? []);
  let hours = $derived(
    hoursFromCells(
      cells,
      scope === 'all' ? undefined : scope === 'weekday' ? (wd) => wd < 5 : (wd) => wd >= 5
    )
  );
  let max = $derived(Math.max(1, ...hours));
  let total = $derived(hours.reduce((a, b) => a + b, 0));
  let levelScale = $derived(scaleQuantize<number>().domain([0, max]).range([1, 2, 3, 4, 5]));
  let peakHour = $derived(hours.indexOf(max));

  function angle(hour: number): number {
    // Hour 0 at the top, clockwise — like a real clock face.
    return (hour * 15 - 90) * (Math.PI / 180);
  }
  function point(hour: number, r: number): { x: number; y: number } {
    const a = angle(hour);
    return { x: C + r * Math.cos(a), y: C + r * Math.sin(a) };
  }
  function barLen(count: number): number {
    if (count <= 0) return 0;
    // Minimum visible stub so tiny values still read as "some activity".
    return Math.max(10, (count / max) * MAX_LEN);
  }
  function levelOf(count: number): number {
    return count <= 0 ? 0 : levelScale(count);
  }
  function fmtHour(h: number): string {
    if ($use24HourClock) return `${String(h).padStart(2, '0')}:00`;
    return h === 0 ? '12am' : h < 12 ? `${h}am` : h === 12 ? '12pm' : `${h - 12}pm`;
  }

  // ── Hover ──────────────────────────────────────────────────────────────────
  let wrapEl = $state<HTMLDivElement | null>(null);
  let tip = $state<{ x: number; y: number; hour: number; count: number } | null>(null);

  function onBar(e: MouseEvent, hour: number) {
    if (!wrapEl) return;
    const r = wrapEl.getBoundingClientRect();
    tip = { x: e.clientX - r.left, y: e.clientY - r.top, hour, count: hours[hour] };
  }
</script>

<ChartCard title={$t('goalsAnalytics.slides.seasonality')}>
  {#snippet icon()}<Clock size={15} />{/snippet}
  {#snippet actions()}
    <div class="clk-scope">
      {#each SCOPES as s (s)}
        <button
          type="button"
          class="clk-scope-btn"
          class:active={scope === s}
          onclick={() => (scope = s)}>{$t(`goalsAnalytics.clock.${s}`)}</button
        >
      {/each}
    </div>
  {/snippet}

  {#if total === 0}
    <div class="chart-empty">
      <Clock size={22} style="opacity:0.25" />
      <span>{$t('goalsAnalytics.seasonality.empty')}</span>
    </div>
  {:else}
    <div class="clk-wrap" bind:this={wrapEl}>
      <svg
        viewBox="0 0 {SIZE} {SIZE}"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={$t('goalsAnalytics.slides.seasonality')}
      >
        <circle cx={C} cy={C} r={R0 - 14} class="clk-face" />

        {#each TICK_HOURS as h (h)}
          {@const p = point(h, LABEL_R)}
          <text x={p.x} y={p.y + 4} class="tick" text-anchor="middle">{fmtHour(h)}</text>
        {/each}

        {#each hours as count, h (h)}
          {@const trackEnd = point(h, R0 + MAX_LEN)}
          {@const barEnd = point(h, R0 + barLen(count))}
          {@const barStart = point(h, R0)}
          <line
            x1={barStart.x}
            y1={barStart.y}
            x2={trackEnd.x}
            y2={trackEnd.y}
            class="clk-track"
          />
          {#if count > 0}
            <line
              x1={barStart.x}
              y1={barStart.y}
              x2={barEnd.x}
              y2={barEnd.y}
              class="clk-bar lv{levelOf(count)}"
            />
          {/if}
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <line
            x1={barStart.x}
            y1={barStart.y}
            x2={trackEnd.x}
            y2={trackEnd.y}
            class="clk-hit"
            onmouseenter={(e) => onBar(e, h)}
            onmousemove={(e) => onBar(e, h)}
            onmouseleave={() => (tip = null)}
          />
        {/each}

        <text x={C} y={C - 8} class="clk-peak" text-anchor="middle"
          >{total > 0 ? fmtHour(peakHour) : '—'}</text
        >
        <text x={C} y={C + 14} class="clk-peak-label" text-anchor="middle"
          >{$t('goalsAnalytics.clock.peakLabel')}</text
        >
      </svg>

      <ChartTooltip x={tip?.x ?? 0} y={tip?.y ?? 0} visible={!!tip} placeBelow={(tip?.y ?? 0) < 60}>
        {#if tip}
          <span class="tt-title">{fmtHour(tip.hour)}</span>
          <span class="tt-row"
            >{$t('goalsAnalytics.clock.events', { values: { count: tip.count } })}</span
          >
        {/if}
      </ChartTooltip>
    </div>
  {/if}
</ChartCard>

<style>
  .clk-wrap {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  svg {
    height: 100%;
    max-height: 440px;
    width: auto;
    max-width: 100%;
  }
  .clk-face {
    fill: color-mix(in srgb, var(--text-primary) 4%, transparent);
    stroke: var(--border);
    stroke-width: 1;
  }
  .tick {
    fill: var(--text-muted);
    font-size: 9px;
    font-family: var(--font-mono);
  }
  .clk-track {
    stroke: color-mix(in srgb, var(--text-primary) 7%, transparent);
    stroke-width: 12;
    stroke-linecap: round;
  }
  .clk-bar {
    stroke-width: 12;
    stroke-linecap: round;
    transition: all 0.3s ease;
  }
  .clk-hit {
    stroke: transparent;
    stroke-width: 14;
    stroke-linecap: round;
  }
  .lv1 {
    stroke: color-mix(in srgb, var(--xp) 30%, transparent);
  }
  .lv2 {
    stroke: color-mix(in srgb, var(--xp) 48%, transparent);
  }
  .lv3 {
    stroke: color-mix(in srgb, var(--xp) 65%, transparent);
  }
  .lv4 {
    stroke: color-mix(in srgb, var(--xp) 85%, transparent);
  }
  .lv5 {
    stroke: var(--xp);
  }
  .clk-peak {
    fill: var(--text-primary);
    font-size: 22px;
    font-weight: 700;
    font-family: var(--font-mono);
  }
  .clk-peak-label {
    fill: var(--text-muted);
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-family: var(--font-mono);
  }
  .clk-scope {
    display: flex;
    gap: 4px;
  }
  .clk-scope-btn {
    padding: 2px 8px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted);
    font-size: 9px;
    font-weight: 700;
    font-family: var(--font-mono);
    cursor: pointer;
    transition: all 0.15s;
  }
  .clk-scope-btn:hover {
    color: var(--text-secondary);
    border-color: var(--text-muted);
  }
  .clk-scope-btn.active {
    background: color-mix(in srgb, var(--xp) 15%, transparent);
    color: var(--xp);
    border-color: var(--xp);
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
