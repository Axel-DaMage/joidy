<script lang="ts">
  /**
   * Timed day/week grid (#1658): Google-Calendar-style hour ruler with
   * positioned event blocks. `columns` holds the day keys — one for day
   * view, seven for week view. All-day / timeless items live in the top
   * strip; timed items are absolutely positioned inside each column.
   */
  import type { CalendarDayMetrics, CalendarTask, PlanSuggestion } from '$lib/api';
  import type { DayItem } from './types';
  import DayBadges from './DayBadges.svelte';
  import Lock from 'lucide-svelte/icons/lock';
  import Repeat from 'lucide-svelte/icons/repeat';
  import Sparkles from 'lucide-svelte/icons/sparkles';
  import { t } from 'svelte-i18n';

  const DAY_MINUTES = 24 * 60;
  const HOURS = Array.from({ length: 24 }, (_, i) => i);
  const HOUR_PX = 44;

  let {
    columns,
    itemsByDay,
    metricsByDay,
    planByDay,
    todayKey,
    selectedDay,
    dropTargetKey,
    draggedTaskId,
    showMetrics,
    compact = false,
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
    columns: { key: string; label: string; sublabel?: string }[];
    itemsByDay: Map<string, DayItem[]>;
    metricsByDay: Map<string, CalendarDayMetrics>;
    planByDay: Map<string, PlanSuggestion[]>;
    todayKey: string;
    selectedDay: string | null;
    dropTargetKey: string | null;
    draggedTaskId: number | null;
    showMetrics: boolean;
    compact?: boolean;
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

  function split(items: DayItem[]): { allDay: DayItem[]; timed: DayItem[] } {
    return {
      allDay: items.filter((i) => i.allDay || i.startMin === null),
      timed: items.filter((i) => !i.allDay && i.startMin !== null),
    };
  }

  function blockStyle(item: DayItem): string {
    const start = Math.max(0, Math.min(DAY_MINUTES - 15, item.startMin ?? 0));
    const end = item.endMin !== null && item.endMin > start ? item.endMin : start + 60;
    const top = (start / DAY_MINUTES) * 100;
    const height = Math.max(((Math.min(end, DAY_MINUTES) - start) / DAY_MINUTES) * 100, 1.4);
    const color = item.color ? `border-left-color: ${item.color};` : '';
    return `top:${top}%;height:${height}%;${color}`;
  }

  function priorityClass(item: DayItem): string {
    if (item.kind !== 'task') return '';
    return `prio-${item.task.priority.toLowerCase()}`;
  }
</script>

<div class="time-grid" class:compact>
  <div class="tg-header" style="grid-template-columns: 40px repeat({columns.length}, 1fr);">
    <span class="tg-gutter"></span>
    {#each columns as col (col.key)}
      <button
        class="tg-col-head"
        class:today={col.key === todayKey}
        class:selected={selectedDay === col.key}
        onclick={() => onSelectDay(col.key)}
      >
        <span class="tg-col-label">{col.label}</span>
        {#if col.sublabel}<span class="caption tg-col-sub">{col.sublabel}</span>{/if}
        {#if showMetrics && metricsByDay.get(col.key)}
          <DayBadges metrics={metricsByDay.get(col.key)} />
        {/if}
      </button>
    {/each}
  </div>

  <div class="tg-allday" style="grid-template-columns: 40px repeat({columns.length}, 1fr);">
    <span class="tg-gutter caption">{$t('calendar.allDay')}</span>
    {#each columns as col (col.key)}
      {@const parts = split(itemsByDay.get(col.key) ?? [])}
      <div class="tg-allday-cell">
        {#each parts.allDay as item}
          <button
            class="tg-pill"
            class:google={item.kind === 'google'}
            class:done={item.kind === 'task' && item.task.done}
            title={item.label}
            onclick={(e) => {
              e.stopPropagation();
              onOpenItem(item);
            }}
          >
            {#if item.kind === 'google'}<Lock size={8} />{:else if item.task.recurrence !== 'NONE'}<Repeat size={8} />{/if}
            <span class="tg-pill-label">{item.label}</span>
          </button>
        {/each}
      </div>
    {/each}
  </div>

  <div class="tg-scroll">
    <div
      class="tg-body"
      style="grid-template-columns: 40px repeat({columns.length}, 1fr); height: {HOURS.length *
        HOUR_PX}px;"
    >
      <div class="tg-hours">
        {#each HOURS as h}
          <span class="tg-hour caption" style="top: {h * HOUR_PX}px;"
            >{String(h).padStart(2, '0')}:00</span
          >
        {/each}
      </div>
      {#each columns as col (col.key)}
        {@const parts = split(itemsByDay.get(col.key) ?? [])}
        <div
          class="tg-col"
          class:today={col.key === todayKey}
          class:drop-target={dropTargetKey === col.key}
          role="region"
          aria-label={col.key}
          ondragover={(e) => onCellDragOver(e, col.key)}
          ondragleave={() => onCellDragLeave(col.key)}
          ondrop={(e) => onCellDrop(e, col.key)}
        >
          {#each HOURS as h}
            <span class="tg-line" style="top: {h * HOUR_PX}px;"></span>
          {/each}
          {#each parts.timed as item}
            <button
              class="tg-block {priorityClass(item)}"
              class:google={item.kind === 'google'}
              class:done={item.kind === 'task' && item.task.done}
              class:dragging={item.kind === 'task' && draggedTaskId === item.task.id}
              style={blockStyle(item)}
              draggable={item.kind === 'task'}
              ondragstart={(e) => {
                if (item.kind === 'task') onTaskDragStart(e, item.task);
              }}
              ondragend={onTaskDragEnd}
              onclick={(e) => {
                e.stopPropagation();
                onOpenItem(item);
              }}
              title={item.label}
            >
              {#if item.kind === 'google'}<Lock size={8} />{:else if item.task.recurrence !== 'NONE'}<Repeat size={8} />{/if}
              <span class="tg-block-label">{item.label}</span>
              {#if item.time}<span class="tg-block-time">{item.time}</span>{/if}
            </button>
          {/each}
          {#each planByDay.get(col.key) ?? [] as sugg (sugg.task_id)}
            {@const start = (parseInt(sugg.start_time.slice(0, 2), 10) * 60 +
              parseInt(sugg.start_time.slice(3, 5), 10)) |
              0}
            {@const end = sugg.end_time
              ? parseInt(sugg.end_time.slice(0, 2), 10) * 60 +
                parseInt(sugg.end_time.slice(3, 5), 10)
              : start + 30}
            <button
              class="tg-block tg-ghost"
              style="top: {(start / DAY_MINUTES) * 100}%; height: {Math.max(
                ((Math.min(end, DAY_MINUTES) - start) / DAY_MINUTES) * 100,
                1.4
              )}%;"
              title={sugg.rationale || $t('calendar.planAcceptHint')}
              onclick={(e) => {
                e.stopPropagation();
                onAcceptSuggestion(sugg);
              }}
            >
              <Sparkles size={8} />
              <span class="tg-block-label">{taskTitle(sugg.task_id)}</span>
              <span class="tg-block-time">{sugg.start_time}</span>
            </button>
          {/each}
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .time-grid {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
  }

  .tg-header {
    display: grid;
    gap: 4px;
    flex-shrink: 0;
    margin-bottom: 4px;
  }

  .tg-col-head {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    border: 1px solid transparent;
    border-radius: calc(var(--r) * 0.6);
    background: transparent;
    color: var(--text-primary);
    cursor: pointer;
    padding: 3px 2px;
  }

  .tg-col-head:hover {
    background: var(--hover);
  }

  .tg-col-head.today {
    border-color: var(--xp);
  }

  .tg-col-head.selected {
    background: var(--xp);
    color: var(--bg);
  }

  .tg-col-label {
    font-size: 11px;
    font-weight: 600;
  }

  .tg-col-sub {
    font-size: 9px;
  }

  .tg-allday {
    display: grid;
    gap: 4px;
    flex-shrink: 0;
    margin-bottom: 4px;
  }

  .tg-gutter {
    font-size: 8px;
    color: var(--text-muted);
    text-align: right;
    padding-right: 4px;
  }

  .tg-allday-cell {
    display: flex;
    flex-wrap: wrap;
    gap: 2px;
    min-height: 18px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 3px;
  }

  .tg-pill {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: 9px;
    padding: 1px 6px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface-2, rgba(255, 255, 255, 0.04));
    color: var(--text-primary);
    cursor: pointer;
    max-width: 100%;
  }

  .tg-pill.google {
    color: var(--text-muted);
  }

  .tg-pill.done {
    text-decoration: line-through;
    opacity: 0.55;
  }

  .tg-pill-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tg-scroll {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }

  .tg-body {
    display: grid;
    position: relative;
  }

  .tg-hours {
    position: relative;
  }

  .tg-hour {
    position: absolute;
    right: 4px;
    transform: translateY(-50%);
    font-size: 8px;
  }

  .tg-col {
    position: relative;
    border-left: 1px solid var(--border);
  }

  .tg-col.today {
    background: color-mix(in srgb, var(--xp) 5%, transparent);
  }

  .tg-col.drop-target {
    background: color-mix(in srgb, var(--xp) 16%, transparent);
  }

  .tg-line {
    position: absolute;
    left: 0;
    right: 0;
    height: 1px;
    background: var(--border);
    opacity: 0.4;
    pointer-events: none;
  }

  .tg-block {
    position: absolute;
    left: 2px;
    right: 2px;
    display: flex;
    align-items: flex-start;
    gap: 3px;
    padding: 2px 4px;
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 3px;
    background: color-mix(in srgb, var(--accent) 18%, var(--surface));
    color: var(--text-primary);
    font-size: 9px;
    cursor: pointer;
    overflow: hidden;
    text-align: left;
    z-index: 1;
  }

  .tg-block.google {
    border-left-color: var(--text-muted);
    background: color-mix(in srgb, var(--text-muted) 14%, var(--surface));
    color: var(--text-muted);
  }

  .tg-block.done {
    opacity: 0.55;
    text-decoration: line-through;
  }

  .tg-block.dragging {
    opacity: 0.35;
  }

  .tg-block.prio-urgent {
    border-left-color: #d9534f;
  }
  .tg-block.prio-high {
    border-left-color: #e08c3a;
  }

  .tg-block-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    font-weight: 600;
  }

  .tg-block-time {
    font-size: 8px;
    opacity: 0.7;
    flex-shrink: 0;
  }

  .tg-ghost {
    border: 1px dashed var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    color: var(--accent);
  }
</style>
