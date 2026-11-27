<script lang="ts">
  /**
   * Mini-month navigator (#1658): compact month grid in the left rail.
   * Clicking a day selects it; arrows page months without touching the main
   * view's range. Productivity dots mark days with activity.
   */
  import type { CalendarDayMetrics } from '$lib/api';
  import { miniMonthCells, densityScore } from './types';
  import ChevronLeft from 'lucide-svelte/icons/chevron-left';
  import ChevronRight from 'lucide-svelte/icons/chevron-right';
  import { t } from 'svelte-i18n';

  let {
    year,
    month,
    todayKey,
    selectedDay,
    metricsByDay,
    onSelectDay,
    onPrevMonth,
    onNextMonth,
  }: {
    year: number;
    month: number;
    todayKey: string;
    selectedDay: string | null;
    metricsByDay: Map<string, CalendarDayMetrics>;
    onSelectDay: (dayKey: string) => void;
    onPrevMonth: () => void;
    onNextMonth: () => void;
  } = $props();

  let cells = $derived(miniMonthCells(year, month));
</script>

<div class="mini-month">
  <div class="mini-header">
    <button class="mini-nav" onclick={onPrevMonth} aria-label={$t('calendar.prevMonth')}>
      <ChevronLeft size={12} />
    </button>
    <span class="mini-title">{$t(`calendar.months.${month}`)} {year}</span>
    <button class="mini-nav" onclick={onNextMonth} aria-label={$t('calendar.nextMonth')}>
      <ChevronRight size={12} />
    </button>
  </div>
  <div class="mini-grid" role="grid" aria-label={$t('calendar.miniMonthLabel')}>
    {#each Array(7) as _, i}
      <span class="mini-weekday caption">{$t(`calendar.weekDaysMin.${i}`)}</span>
    {/each}
    {#each cells as cell}
      {#if cell === null}
        <span class="mini-blank"></span>
      {:else}
        <button
          class="mini-day"
          class:today={cell.key === todayKey}
          class:selected={cell.key === selectedDay}
          onclick={() => onSelectDay(cell.key)}
          aria-label={cell.key}
        >
          {cell.day}
          {#if densityScore(metricsByDay.get(cell.key)) > 0}
            <span
              class="mini-dot"
              style="opacity: {0.35 + densityScore(metricsByDay.get(cell.key)) * 0.65}"
            ></span>
          {/if}
        </button>
      {/if}
    {/each}
  </div>
</div>

<style>
  .mini-month {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .mini-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .mini-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: capitalize;
  }

  .mini-nav {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 2px;
    display: flex;
    align-items: center;
    border-radius: 4px;
  }

  .mini-nav:hover {
    color: var(--text-primary);
    background: var(--hover);
  }

  .mini-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 1px;
  }

  .mini-weekday {
    text-align: center;
    font-size: 8px;
    padding: 2px 0;
  }

  .mini-day {
    position: relative;
    aspect-ratio: 1;
    border: none;
    background: transparent;
    color: var(--text-primary);
    font-size: 9px;
    cursor: pointer;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
  }

  .mini-day:hover {
    background: var(--hover);
  }

  .mini-day.today {
    color: var(--xp);
    font-weight: 700;
    box-shadow: inset 0 0 0 1px var(--xp);
  }

  .mini-day.selected {
    background: var(--xp);
    color: var(--bg);
    font-weight: 700;
  }

  .mini-dot {
    position: absolute;
    bottom: 2px;
    left: 50%;
    transform: translateX(-50%);
    width: 3px;
    height: 3px;
    border-radius: 50%;
    background: var(--accent);
  }
</style>
