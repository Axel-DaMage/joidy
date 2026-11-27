<script lang="ts">
  /**
   * Year view (#1658): 12 mini-months; day cells carry a productivity dot.
   * Clicking a day selects it and jumps into month view (via onJumpToMonth).
   */
  import type { CalendarDayMetrics } from '$lib/api';
  import { miniMonthCells, densityScore } from './types';
  import { t } from 'svelte-i18n';

  let {
    year,
    todayKey,
    selectedDay,
    metricsByDay,
    onSelectDay,
    onJumpToMonth,
  }: {
    year: number;
    todayKey: string;
    selectedDay: string | null;
    metricsByDay: Map<string, CalendarDayMetrics>;
    onSelectDay: (dayKey: string) => void;
    onJumpToMonth: (month: number, dayKey?: string) => void;
  } = $props();

  const MONTHS = Array.from({ length: 12 }, (_, i) => i);
</script>

<div class="year-grid">
  {#each MONTHS as m}
    <div class="year-month">
      <button class="year-month-title" onclick={() => onJumpToMonth(m)}>
        {$t(`calendar.months.${m}`)}
      </button>
      <div class="year-mini-grid">
        {#each miniMonthCells(year, m) as cell}
          {#if cell === null}
            <span class="ym-blank"></span>
          {:else}
            {@const density = densityScore(metricsByDay.get(cell.key))}
            <button
              class="ym-day"
              class:today={cell.key === todayKey}
              class:selected={cell.key === selectedDay}
              class:active={density > 0}
              style={density > 0
                ? `background: color-mix(in srgb, var(--accent) ${Math.round(density * 55 + 8)}%, transparent);`
                : ''}
              title={cell.key}
              onclick={() => onSelectDay(cell.key)}
            >
              {cell.day}
            </button>
          {/if}
        {/each}
      </div>
    </div>
  {/each}
</div>

<style>
  .year-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--s3);
    overflow-y: auto;
    flex: 1;
    min-height: 0;
    padding: 2px;
  }

  .year-month {
    display: flex;
    flex-direction: column;
    gap: 4px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
    padding: var(--s2);
  }

  .year-month-title {
    background: none;
    border: none;
    color: var(--text-primary);
    font-size: 11px;
    font-weight: 600;
    text-transform: capitalize;
    cursor: pointer;
    padding: 2px 4px;
    text-align: left;
    border-radius: 4px;
  }

  .year-month-title:hover {
    background: var(--hover);
    color: var(--xp);
  }

  .year-mini-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 0;
  }

  .ym-day {
    aspect-ratio: 1;
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 8px;
    cursor: pointer;
    border-radius: 50%;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .ym-day.active {
    color: var(--text-primary);
  }

  .ym-day:hover {
    background: var(--hover);
    color: var(--text-primary);
  }

  .ym-day.today {
    color: var(--xp);
    font-weight: 700;
    box-shadow: inset 0 0 0 1px var(--xp);
  }

  .ym-day.selected {
    background: var(--xp) !important;
    color: var(--bg);
    font-weight: 700;
  }

  @media (max-width: 900px) {
    .year-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  @media (max-width: 640px) {
    .year-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }
</style>
