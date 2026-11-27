<script lang="ts">
  /**
   * Month view (#1658): 6×7 day grid with event/task chips, per-day metric
   * badges and an optional productivity-heatmap overlay mode. Task chips are
   * draggable onto other day cells; plan suggestions render as ghost chips.
   */
  import type { CalendarDayMetrics, CalendarTask, PlanSuggestion } from '$lib/api';
  import type { DayItem, GridCell } from './types';
  import { densityScore, moodGlyph } from './types';
  import DayBadges from './DayBadges.svelte';
  import Lock from 'lucide-svelte/icons/lock';
  import Repeat from 'lucide-svelte/icons/repeat';
  import Sparkles from 'lucide-svelte/icons/sparkles';
  import { t } from 'svelte-i18n';

  let {
    cells,
    itemsByDay,
    metricsByDay,
    planByDay,
    todayKey,
    selectedDay,
    dropTargetKey,
    draggedTaskId,
    heatmap,
    showMetrics,
    onSelectDay,
    onOpenItem,
    onTaskDragStart,
    onTaskDragEnd,
    onCellDragOver,
    onCellDragLeave,
    onCellDrop,
    onAcceptSuggestion,
    taskTitle,
  }: {
    cells: GridCell[];
    itemsByDay: Map<string, DayItem[]>;
    metricsByDay: Map<string, CalendarDayMetrics>;
    planByDay: Map<string, PlanSuggestion[]>;
    todayKey: string;
    selectedDay: string | null;
    dropTargetKey: string | null;
    draggedTaskId: number | null;
    heatmap: boolean;
    showMetrics: boolean;
    onSelectDay: (dayKey: string) => void;
    onOpenItem: (item: DayItem) => void;
    onTaskDragStart: (e: DragEvent, task: CalendarTask) => void;
    onTaskDragEnd: () => void;
    onCellDragOver: (e: DragEvent, dayKey: string) => void;
    onCellDragLeave: (dayKey: string) => void;
    onCellDrop: (e: DragEvent, dayKey: string) => void;
    onAcceptSuggestion: (s: PlanSuggestion) => void;
    taskTitle: (taskId: number) => string;
  } = $props();

  function priorityClass(item: DayItem): string {
    if (item.kind !== 'task') return '';
    return `prio prio-${item.task.priority.toLowerCase()}`;
  }

  function chipStyle(item: DayItem): string {
    return item.color ? `border-left: 2px solid ${item.color};` : '';
  }

  function heatStyle(metrics: CalendarDayMetrics | undefined): string {
    const score = densityScore(metrics);
    if (score <= 0) return '';
    // Productivity density: accent intensity scaled by the score.
    return `background: color-mix(in srgb, var(--accent) ${Math.round(score * 45 + 6)}%, transparent);`;
  }
</script>

<div class="weekday-row">
  {#each Array(7) as _, i}
    <span class="weekday caption">{$t(`calendar.weekDays.${i}`)}</span>
  {/each}
</div>

<div class="day-grid">
  {#each cells as cell (cell.key)}
    {@const items = itemsByDay.get(cell.key) ?? []}
    {@const metrics = metricsByDay.get(cell.key)}
    <button
      class="day-cell"
      class:out={!cell.inMonth}
      class:today={cell.key === todayKey}
      class:selected={selectedDay === cell.key}
      class:drop-target={dropTargetKey === cell.key}
      class:heat={heatmap}
      style={heatmap ? heatStyle(metrics) : ''}
      draggable={items.some((i) => i.kind === 'task')}
      ondragover={(e) => onCellDragOver(e, cell.key)}
      ondragleave={() => onCellDragLeave(cell.key)}
      ondrop={(e) => onCellDrop(e, cell.key)}
      onclick={() => onSelectDay(cell.key)}
    >
      <span class="day-head">
        <span class="day-num">{cell.day}</span>
        {#if heatmap && metrics?.mood_score}
          <span class="day-mood">{moodGlyph(metrics.mood_score)}</span>
        {/if}
      </span>
      <span class="cell-items">
        {#each items.slice(0, heatmap ? 1 : 3) as item}
          {#if item.kind === 'google'}
            <span
              class="chip chip-google"
              style={chipStyle(item)}
              role="button"
              tabindex="-1"
              onclick={(e) => {
                e.stopPropagation();
                onOpenItem(item);
              }}
              onkeydown={(e) => {
                if (e.key === 'Enter') {
                  e.stopPropagation();
                  onOpenItem(item);
                }
              }}><Lock size={8} />{item.label}</span
            >
          {:else}
            <span
              class="chip {priorityClass(item)}"
              class:done={item.task.done}
              class:dragging={draggedTaskId === item.task.id}
              style={chipStyle(item)}
              role="button"
              tabindex="-1"
              draggable="true"
              ondragstart={(e) => onTaskDragStart(e, item.task)}
              ondragend={onTaskDragEnd}
              onclick={(e) => {
                e.stopPropagation();
                onOpenItem(item);
              }}
              onkeydown={(e) => {
                if (e.key === 'Enter') {
                  e.stopPropagation();
                  onOpenItem(item);
                }
              }}
              >{#if item.task.recurrence !== 'NONE'}<Repeat
                  size={8}
                  class="recur-icon"
                />{/if}{item.label}</span
            >
          {/if}
        {/each}
        {#if items.length > (heatmap ? 1 : 3)}
          <span class="chip chip-more">+{items.length - (heatmap ? 1 : 3)}</span>
        {/if}
        {#each planByDay.get(cell.key) ?? [] as sugg (sugg.task_id)}
          <span
            class="chip chip-ghost"
            role="button"
            tabindex="-1"
            title={sugg.rationale || $t('calendar.planAcceptHint')}
            onclick={(e) => {
              e.stopPropagation();
              onAcceptSuggestion(sugg);
            }}
            onkeydown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.stopPropagation();
                onAcceptSuggestion(sugg);
              }
            }}
            ><Sparkles size={7} />{sugg.start_time} {taskTitle(sugg.task_id)}</span
          >
        {/each}
      </span>
      {#if showMetrics}
        <DayBadges {metrics} />
      {/if}
    </button>
  {/each}
</div>

<style>
  .weekday-row {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 4px;
    margin-bottom: 4px;
    flex-shrink: 0;
  }

  .weekday {
    text-align: center;
    font-size: 11px;
  }

  .day-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    grid-template-rows: repeat(6, 1fr);
    gap: 4px;
    flex: 1;
    min-height: 0;
  }

  .day-cell {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    justify-content: flex-start;
    gap: 2px;
    padding: 3px 4px;
    border: 1px solid transparent;
    border-radius: calc(var(--r) * 0.6);
    background: transparent;
    cursor: pointer;
    color: var(--text-primary);
    font-size: 11px;
    min-height: 0;
    overflow: hidden;
    text-align: left;
  }

  .day-cell:hover {
    background: var(--hover);
  }

  .day-cell.heat:hover {
    background: unset;
    filter: brightness(1.15);
  }

  .day-cell.out {
    color: var(--text-muted);
    opacity: 0.5;
  }

  .day-cell.today {
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 12%, transparent);
  }

  .day-cell.today .day-num {
    color: var(--xp);
    font-weight: 700;
  }

  .day-cell.selected {
    background: var(--xp);
    color: var(--bg);
  }

  .day-cell.selected .day-num,
  .day-cell.selected .day-mood {
    color: var(--bg);
    font-weight: 700;
  }

  .day-cell.selected .chip {
    background: rgba(0, 0, 0, 0.15);
    color: var(--bg);
  }

  .day-cell.selected:hover {
    background: var(--xp-2);
  }

  .day-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
  }

  .day-num {
    font-size: 12px;
  }

  .day-mood {
    font-size: 9px;
  }

  .cell-items {
    display: flex;
    flex-direction: column;
    gap: 1px;
    width: 100%;
    min-width: 0;
  }

  .chip {
    display: flex;
    align-items: center;
    gap: 3px;
    font-size: 9px;
    line-height: 1.2;
    padding: 0 3px;
    border-radius: 3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
    background: color-mix(in srgb, var(--text-muted) 15%, transparent);
  }

  .chip-google {
    color: var(--text-muted);
  }

  .chip.done {
    text-decoration: line-through;
    opacity: 0.55;
  }

  .chip.dragging {
    opacity: 0.35;
  }

  .day-cell.drop-target {
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 18%, transparent);
  }

  .chip-more {
    color: var(--text-muted);
    background: transparent;
  }

  .prio-low {
    color: var(--text-muted);
  }
  .prio-medium {
    color: var(--accent);
    font-style: italic;
  }
  .prio-high {
    color: #e08c3a;
    font-weight: 600;
  }
  .prio-urgent {
    color: #d9534f;
    font-weight: 700;
    text-decoration: underline;
  }

  .chip-ghost {
    border: 1px dashed var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    color: var(--accent);
    opacity: 0.8;
    cursor: pointer;
  }

  .chip-ghost:hover {
    opacity: 1;
    background: color-mix(in srgb, var(--accent) 22%, transparent);
  }
</style>
