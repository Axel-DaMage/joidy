<script lang="ts">
  import CalendarRange from 'lucide-svelte/icons/calendar-range';
  import ChartCard from './ChartCard.svelte';
  import ChartTooltip from './ChartTooltip.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { parseLocalDate } from '$lib/utils/date';
  import { locale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';

  // Weekly rhythm (#1499): XP per ISO week (Monday start). Bar height is the
  // week's XP, bar brightness is how many of its 7 days were active — so a
  // tall-but-dim bar is "one big day", a tall-and-bright bar is steady work.
  type DayRow = AnalyticsOverview['daily_activity'][number];

  let { activity }: { activity?: DayRow[] } = $props();

  interface Week {
    start: Date;
    xp: number;
    active: number;
    days: number;
  }

  let weeks = $derived.by<Week[]>(() => {
    const map = new Map<string, Week>();
    for (const d of activity ?? []) {
      const date = parseLocalDate(d.date);
      const start = new Date(date);
      start.setDate(date.getDate() - ((date.getDay() + 6) % 7));
      const key = start.toDateString();
      const w = map.get(key) ?? { start, xp: 0, active: 0, days: 0 };
      w.xp += Math.max(0, d.xp);
      w.days += 1;
      if (d.events > 0 || d.xp !== 0) w.active += 1;
      map.set(key, w);
    }
    return [...map.values()];
  });
  let max = $derived(Math.max(1, ...weeks.map((w) => w.xp)));
  let avg = $derived(weeks.length ? weeks.reduce((a, w) => a + w.xp, 0) / weeks.length : 0);
  let bestIdx = $derived(weeks.findIndex((w) => w.xp === Math.max(...weeks.map((x) => x.xp))));
  let hasData = $derived(weeks.some((w) => w.xp > 0));

  let monthFmt = $derived(new Intl.DateTimeFormat($locale, { month: 'short' }));
  let dayFmt = $derived(new Intl.DateTimeFormat($locale, { day: 'numeric', month: 'short' }));
  // Month name under the first week of each month, skipped when it would
  // collide with the previous label.
  let monthLabels = $derived.by(() => {
    let last = -99;
    return weeks.map((w, i) => {
      const newMonth = i === 0 || w.start.getMonth() !== weeks[i - 1].start.getMonth();
      if (!newMonth || i - last < (weeks.length > 40 ? 5 : 3)) return '';
      last = i;
      return monthFmt.format(w.start).replace('.', '');
    });
  });

  let wrapEl = $state<HTMLDivElement | null>(null);
  let tip = $state<{ x: number; y: number; w: Week } | null>(null);
  function onBar(e: MouseEvent, w: Week) {
    if (!wrapEl) return;
    const r = wrapEl.getBoundingClientRect();
    const c = (e.currentTarget as HTMLElement).getBoundingClientRect();
    tip = { x: c.left - r.left + c.width / 2, y: c.top - r.top, w };
  }
</script>

<ChartCard title={$t('analyticsPage.weekly.title')}>
  {#snippet icon()}<CalendarRange size={13} />{/snippet}
  {#snippet actions()}
    {#if hasData}
      <span class="wr-avg mono"
        >{$t('analyticsPage.weekly.avg', { values: { xp: Math.round(avg).toLocaleString() } })}</span
      >
    {/if}
  {/snippet}

  {#if !hasData}
    <div class="chart-empty"><span>{$t('analyticsPage.weekday.empty')}</span></div>
  {:else}
    <div class="wr-wrap" bind:this={wrapEl}>
      <div class="wr-plot">
        <div class="wr-avgline" style:bottom="{(avg / max) * 100}%"></div>
        {#each weeks as w, i (w.start.getTime())}
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div
            class="wr-col"
            class:best={i === bestIdx}
            onmouseenter={(e) => onBar(e, w)}
            onmouseleave={() => (tip = null)}
          >
            <div
              class="wr-bar"
              style:height="{Math.max(w.xp > 0 ? 3 : 1, (w.xp / max) * 100)}%"
              style:--b={0.3 + 0.7 * (w.active / Math.max(1, w.days))}
              style:--i={i}
            ></div>
          </div>
        {/each}
      </div>
      <div class="wr-axis">
        {#each weeks as _w, i (i)}
          <span class="wr-tick mono">{monthLabels[i]}</span>
        {/each}
      </div>

      <ChartTooltip x={tip?.x ?? 0} y={tip?.y ?? 0} visible={!!tip}>
        {#if tip}
          <span class="tt-title">{$t('analyticsPage.weekly.weekOf', { values: { date: dayFmt.format(tip.w.start) } })}</span>
          <span class="tt-row"
            ><span class="tt-dot" style="background: var(--xp)"></span>{$t(
              'analyticsPage.heatmap.xpOn',
              { values: { xp: tip.w.xp.toLocaleString() } }
            )}</span
          >
          <span class="tt-row"
            >{$t('analyticsPage.weekly.activeDays', {
              values: { count: tip.w.active, total: tip.w.days },
            })}</span
          >
        {/if}
      </ChartTooltip>
    </div>
  {/if}
</ChartCard>

<style>
  .wr-wrap {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .wr-plot {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    align-items: stretch;
    gap: 3px;
    border-bottom: 1px solid var(--border);
  }
  .wr-avgline {
    position: absolute;
    left: 0;
    right: 0;
    border-top: 1px dashed color-mix(in srgb, var(--text-muted) 70%, transparent);
    pointer-events: none;
    z-index: 1;
  }
  .wr-col {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: flex-end;
  }
  .wr-bar {
    width: 100%;
    border-radius: 2px 2px 0 0;
    background: color-mix(in srgb, var(--xp) calc(var(--b) * 100%), transparent);
    transform-origin: bottom;
    animation: wr-grow 0.7s cubic-bezier(0.2, 0.7, 0.2, 1) both;
    animation-delay: calc(var(--i) * 14ms);
    transition: filter 0.15s;
  }
  .wr-col:hover .wr-bar {
    background: var(--xp);
  }
  .wr-axis {
    display: flex;
    gap: 3px;
    height: 12px;
    flex-shrink: 0;
  }
  .wr-tick {
    flex: 1;
    min-width: 0;
    font-size: 10px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: visible;
    text-transform: capitalize;
  }
  .wr-avg {
    font-size: 10px;
    font-weight: 600;
    text-transform: none;
    letter-spacing: 0;
    color: var(--text-muted);
  }
  .chart-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    font-size: 12px;
  }
  @keyframes wr-grow {
    from {
      transform: scaleY(0);
    }
    to {
      transform: scaleY(1);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .wr-bar {
      animation: none;
    }
  }
</style>
