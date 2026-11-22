<script lang="ts">
  import { scaleQuantize } from 'd3';
  import CalendarCheck from 'lucide-svelte/icons/calendar-check';
  import ChartCard from './ChartCard.svelte';
  import ChartTooltip from './ChartTooltip.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { localDayKey } from '$lib/utils/date';
  import { locale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';

  // GitHub-style consistency calendar (#1499): weeks as columns, weekday rows
  // (Mon–Sun), intensity by XP quintile. `days` is the parent's global
  // analysis window — it re-fetches /analytics/overview when it changes.
  type DayActivity = AnalyticsOverview['daily_activity'][number];

  let {
    activity = [],
    days = 180,
  }: {
    activity?: DayActivity[];
    days?: number;
  } = $props();

  const WEEKDAY_ROWS = [0, 1, 2, 3, 4, 5, 6] as const; // Mon..Sun

  let byDate = $derived(new Map(activity.map((d) => [d.date, d])));
  let maxXp = $derived(Math.max(1, ...activity.map((d) => d.xp)));
  let levelScale = $derived(
    scaleQuantize<number>().domain([0, maxXp]).range([1, 2, 3, 4, 5])
  );

  function levelOf(cell: Cell): number {
    if (cell.future || !cell.day || cell.day.xp <= 0) return 0;
    return levelScale(cell.day.xp);
  }

  interface Cell {
    key: string;
    date: Date;
    day: DayActivity | null;
    future: boolean;
  }
  interface Week {
    cells: Cell[];
    monthLabel: string;
  }

  let weeks = $derived.by<Week[]>(() => {
    const today = new Date();
    const end = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const rangeStart = new Date(end);
    rangeStart.setDate(end.getDate() - (days - 1));
    // Align the first column to the Monday of the range-start week.
    const gridStart = new Date(rangeStart);
    gridStart.setDate(gridStart.getDate() - ((gridStart.getDay() + 6) % 7));

    const monthFmt = new Intl.DateTimeFormat($locale, { month: 'short' });
    const out: Week[] = [];
    const cursor = new Date(gridStart);
    let prevMonth = -1;
    let lastLabel = -99;
    while (cursor <= end) {
      const cells: Cell[] = [];
      for (let i = 0; i < 7; i++) {
        const key = localDayKey(cursor);
        cells.push({
          key,
          date: new Date(cursor),
          day: byDate.get(key) ?? null,
          future: cursor > end,
        });
        cursor.setDate(cursor.getDate() + 1);
      }
      const month = cells[0].date.getMonth();
      // A month label is skipped when it would sit right next to the previous one.
      const show = month !== prevMonth && out.length - lastLabel >= 3;
      if (show) lastLabel = out.length;
      out.push({ cells, monthLabel: show ? monthFmt.format(cells[0].date) : '' });
      prevMonth = month;
    }
    return out;
  });

  const weekdayFmt = $derived(new Intl.DateTimeFormat($locale, { weekday: 'short' }));
  const dateFmt = $derived(
    new Intl.DateTimeFormat($locale, { weekday: 'long', day: 'numeric', month: 'long' })
  );
  // 2024-01-01 was a Monday — index 0..6 maps to Mon..Sun in any locale.
  const weekdayLabel = (i: number) => weekdayFmt.format(new Date(2024, 0, 1 + i));

  let tip = $state<{ x: number; y: number; cell: Cell } | null>(null);

  function onCell(e: Event, cell: Cell) {
    const el = e.currentTarget as HTMLElement;
    tip = { x: el.offsetLeft + el.offsetWidth / 2, y: el.offsetTop, cell };
  }

  // Responsive cell size: fit the grid to the card width. Cells may be wider
  // than tall (short windows have few columns); the card height follows the
  // grid so no vertical space is wasted around it.
  let wrapW = $state(0);
  let cellW = $derived.by(() => {
    const cols = weeks.length;
    if (!wrapW || cols === 0) return 11;
    const labelW = 30;
    const gap = 3;
    return Math.max(7, Math.min(46, Math.floor((wrapW - labelW - gap * (cols - 1)) / cols)));
  });
  // Cells grow taller than wide only as far as the card height allows.
  let wrapH = $state(0);
  let cellH = $derived.by(() => {
    const fitH = wrapH > 0 ? Math.floor((wrapH - 43) / 7) : cellW;
    return Math.max(7, Math.min(fitH, Math.round(cellW * 1.6), 40));
  });

  function cellAria(cell: Cell): string {
    const dateStr = dateFmt.format(cell.date);
    if (cell.future || !cell.day || cell.day.xp <= 0) {
      return `${dateStr} — ${$t('goalsAnalytics.heatmap.noData')}`;
    }
    return `${dateStr} — ${$t('goalsAnalytics.heatmap.xpOn', { values: { xp: cell.day.xp } })}`;
  }
</script>

<ChartCard title={$t('goalsAnalytics.slides.consistency')}>
  {#snippet icon()}<CalendarCheck size={15} />{/snippet}

  <div class="hm-wrap" bind:clientWidth={wrapW} bind:clientHeight={wrapH}>
    <div class="hm-grid" style:--cw="{cellW}px" style:--ch="{cellH}px">
      <div class="hm-wd-col">
        <span class="hm-month hm-month-spacer"></span>
        {#each WEEKDAY_ROWS as i (i)}
          <span class="hm-wd">{i % 2 === 0 ? weekdayLabel(i) : ''}</span>
        {/each}
      </div>
      {#each weeks as week, wi (week.cells[0].key)}
        <div class="hm-week" style:--col={wi}>
          <span class="hm-month">{week.monthLabel}</span>
          {#each week.cells as cell (cell.key)}
            <button
              type="button"
              class="hm-cell lv{levelOf(cell)}"
              class:future={cell.future}
              aria-label={cellAria(cell)}
              onmouseenter={(e) => onCell(e, cell)}
              onmouseleave={() => (tip = null)}
              onfocus={(e) => onCell(e, cell)}
              onblur={() => (tip = null)}
            ></button>
          {/each}
        </div>
      {/each}
    </div>

    <ChartTooltip
      x={tip?.x ?? 0}
      y={tip?.y ?? 0}
      visible={!!tip}
      placeBelow={(tip?.y ?? 0) < 60}
    >
      {#if tip}
        <span class="tt-title">{dateFmt.format(tip.cell.date)}</span>
        {#if tip.cell.day && !tip.cell.future && tip.cell.day.xp > 0}
          <span class="tt-row"
            ><span class="tt-dot" style="background: var(--xp)"></span>{$t(
              'goalsAnalytics.heatmap.xpOn',
              { values: { xp: tip.cell.day.xp } }
            )}</span
          >
          <span class="tt-row"
            >{$t('goalsAnalytics.heatmap.events', {
              values: { count: tip.cell.day.events },
            })}</span
          >
          <span class="tt-row"
            >{$t('goalsAnalytics.heatmap.goals', {
              values: { count: tip.cell.day.goals_completed },
            })}</span
          >
          <span class="tt-row"
            >{$t('goalsAnalytics.heatmap.pomodoros', {
              values: { count: tip.cell.day.pomodoros },
            })}</span
          >
          <span class="tt-row"
            >{$t('goalsAnalytics.heatmap.notes', {
              values: { count: tip.cell.day.notes },
            })}</span
          >
        {:else}
          <span class="tt-row">{$t('goalsAnalytics.heatmap.noData')}</span>
        {/if}
      {/if}
    </ChartTooltip>
  </div>

  <div class="hm-legend">
    <span>{$t('goalsAnalytics.heatmap.less')}</span>
    {#each [0, 1, 2, 3, 4, 5] as lv (lv)}
      <span class="hm-cell hm-cell-legend lv{lv}"></span>
    {/each}
    <span>{$t('goalsAnalytics.heatmap.more')}</span>
  </div>
</ChartCard>

<style>
  .hm-wrap {
    position: relative;
    overflow: hidden;
    flex: 1;
    min-height: 0;
    padding: var(--s1) 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .hm-grid {
    display: flex;
    gap: 3px;
    width: max-content;
    --cw: 11px;
    --ch: 11px;
  }
  .hm-wd-col {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding-right: 4px;
    flex-shrink: 0;
  }
  .hm-week {
    display: flex;
    flex-direction: column;
    gap: 3px;
    flex-shrink: 0;
  }
  .hm-month {
    width: var(--cw);
    height: 14px;
    font-size: 9px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    line-height: 14px;
    overflow: visible;
    white-space: nowrap;
  }
  .hm-wd {
    height: var(--ch);
    font-size: 8px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    line-height: var(--ch);
  }
  .hm-cell {
    width: var(--cw);
    height: var(--ch);
    border-radius: var(--r-sm);
    border: none;
    padding: 0;
    cursor: default;
    outline: 1px solid transparent;
    animation: hm-pop 0.45s cubic-bezier(0.2, 0.7, 0.2, 1) both;
    animation-delay: calc(var(--col, 0) * 8ms);
  }
  .hm-cell:hover,
  .hm-cell:focus-visible {
    outline-color: var(--text-secondary);
  }
  .hm-cell.future {
    opacity: 0.35;
  }
  .hm-cell-legend {
    display: inline-block;
    cursor: default;
    width: 11px;
    height: 11px;
    animation: none;
  }
  @keyframes hm-pop {
    from {
      opacity: 0;
      transform: scale(0.5);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .hm-cell {
      animation: none;
    }
  }
  .lv0 {
    background: color-mix(in srgb, var(--text-primary) 7%, transparent);
  }
  .lv1 {
    background: color-mix(in srgb, var(--xp) 25%, transparent);
  }
  .lv2 {
    background: color-mix(in srgb, var(--xp) 42%, transparent);
  }
  .lv3 {
    background: color-mix(in srgb, var(--xp) 60%, transparent);
  }
  .lv4 {
    background: color-mix(in srgb, var(--xp) 80%, transparent);
  }
  .lv5 {
    background: var(--xp);
  }
  .hm-legend {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 3px;
    font-size: 9px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    padding-top: var(--s1);
    flex-shrink: 0;
  }
  .hm-legend .hm-cell {
    pointer-events: none;
  }
</style>
