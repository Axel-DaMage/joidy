<script lang="ts">
  import ChartColumn from 'lucide-svelte/icons/chart-column';
  import ChartCard from './ChartCard.svelte';
  import ChartTooltip from './ChartTooltip.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { avgXpByWeekday } from '$lib/utils/insights';
  import { locale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';

  // Weekday profile (#1499): average XP per calendar day for each day of the
  // week. Averaging per occurrence (not summing) keeps weekdays comparable
  // when the window holds an uneven number of each one.
  type DayRow = AnalyticsOverview['daily_activity'][number];

  let { activity }: { activity?: DayRow[] } = $props();

  let avgs = $derived(avgXpByWeekday(activity ?? []));
  let max = $derived(Math.max(1, ...avgs));
  let best = $derived(avgs.indexOf(Math.max(...avgs)));
  let hasData = $derived(avgs.some((v) => v > 0));
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
  {#snippet icon()}<ChartColumn size={13} />{/snippet}

  {#if !hasData}
    <div class="chart-empty"><span>{$t('goalsAnalytics.weekday.empty')}</span></div>
  {:else}
    <div class="wd-wrap" bind:this={wrapEl}>
      {#each avgs as v, i (i)}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          class="wd-col"
          class:peak={i === best}
          onmouseenter={(e) => onBar(e, i)}
          onmousemove={(e) => onBar(e, i)}
          onmouseleave={() => (tip = null)}
        >
          <span class="wd-val mono">{v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v}</span>
          <div class="wd-track">
            <div class="wd-bar" style:height="{Math.max(3, (v / max) * 100)}%" style:--i={i}></div>
          </div>
          <span class="wd-label">{dayNames[i]}</span>
        </div>
      {/each}

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
    gap: 6px;
  }
  .wd-col {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }
  .wd-val {
    font-size: 9px;
    color: var(--text-muted);
    transition: color 0.2s;
  }
  .wd-track {
    flex: 1;
    width: 100%;
    min-height: 0;
    display: flex;
    align-items: flex-end;
    border-radius: var(--r-sm);
    background: color-mix(in srgb, var(--text-primary) 4%, transparent);
  }
  .wd-bar {
    width: 100%;
    border-radius: var(--r-sm);
    background: color-mix(in srgb, var(--xp) 45%, transparent);
    transform-origin: bottom;
    animation: wd-grow 0.7s cubic-bezier(0.2, 0.7, 0.2, 1) both;
    animation-delay: calc(var(--i) * 45ms);
    transition: filter 0.2s;
  }
  .wd-col:hover .wd-bar {
    background: color-mix(in srgb, var(--xp) 70%, transparent);
  }
  .wd-col:hover .wd-val {
    color: var(--text-primary);
  }
  .wd-col.peak .wd-bar {
    background: var(--xp);
  }
  .wd-col.peak .wd-val {
    color: var(--xp);
    font-weight: 700;
  }
  .wd-label {
    font-size: 9px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    text-transform: capitalize;
  }
  .wd-col.peak .wd-label {
    color: var(--text-primary);
  }
  .chart-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    font-size: 12px;
  }
  @keyframes wd-grow {
    from {
      transform: scaleY(0);
    }
    to {
      transform: scaleY(1);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .wd-bar {
      animation: none;
    }
  }
</style>
