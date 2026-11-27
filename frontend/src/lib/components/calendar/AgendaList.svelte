<script lang="ts">
  /**
   * Agenda/schedule view (#1658): chronological day rows with pills for
   * events/tasks and a per-day metrics strip (progressive disclosure).
   */
  import type { CalendarDayMetrics, PlanSuggestion } from '$lib/api';
  import type { DayItem } from './types';
  import DayBadges from './DayBadges.svelte';
  import Lock from 'lucide-svelte/icons/lock';
  import Repeat from 'lucide-svelte/icons/repeat';
  import Sparkles from 'lucide-svelte/icons/sparkles';
  import { t } from 'svelte-i18n';
  import { locale } from '$lib/stores/locale';

  let {
    days,
    metricsByDay,
    planByDay,
    todayKey,
    selectedDay,
    showMetrics,
    onSelectDay,
    onOpenItem,
    onAcceptSuggestion,
    taskTitle,
  }: {
    days: { date: Date; key: string; items: DayItem[] }[];
    metricsByDay: Map<string, CalendarDayMetrics>;
    planByDay: Map<string, PlanSuggestion[]>;
    todayKey: string;
    selectedDay: string | null;
    showMetrics: boolean;
    onSelectDay: (dayKey: string) => void;
    onOpenItem: (item: DayItem) => void;
    onAcceptSuggestion: (s: PlanSuggestion) => void;
    taskTitle: (taskId: number) => string;
  } = $props();

  function priorityClass(item: DayItem): string {
    if (item.kind !== 'task') return '';
    return `prio prio-${item.task.priority.toLowerCase()}`;
  }
</script>

<div class="agenda-view">
  {#each days as day (day.key)}
    <div
      class="agenda-day-row"
      class:today={day.key === todayKey}
      class:selected={selectedDay === day.key}
      role="button"
      tabindex="0"
      onclick={() => onSelectDay(day.key)}
      onkeydown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelectDay(day.key);
        }
      }}
    >
      <div class="agenda-date-badge">
        <span class="day-num">{day.date.getDate()}</span>
        <span class="caption"
          >{day.date.toLocaleDateString($locale, {
            weekday: 'short',
            month: 'short',
          })}</span
        >
        {#if showMetrics}
          <DayBadges metrics={metricsByDay.get(day.key)} />
        {/if}
      </div>
      <div class="agenda-day-items">
        {#if day.items.length === 0 && (planByDay.get(day.key) ?? []).length === 0}
          <span class="caption empty-agenda-day">{$t('calendar.noEventsDay')}</span>
        {:else}
          {#each day.items as item}
            <button
              class="agenda-item-pill {priorityClass(item)}"
              class:done={item.kind === 'task' && item.task.done}
              title={item.location ? `${item.label} · ${item.location}` : item.label}
              onclick={(e) => {
                e.stopPropagation();
                onOpenItem(item);
              }}
            >
              {#if item.kind === 'google'}
                <Lock size={9} class="lock-icon" />
                <span class="chip-time caption">{item.allDay ? $t('calendar.allDay') : item.time}</span>
                <span class="pill-title">{item.label}</span>
              {:else}
                <span class="priority-dot {priorityClass(item)}"></span>
                {#if item.time}<span class="chip-time caption">{item.time}</span>{/if}
                {#if item.task.recurrence !== 'NONE'}<Repeat size={9} class="recur-icon" />{/if}
                <span class="pill-title">{item.label}</span>
              {/if}
            </button>
          {/each}
          {#each planByDay.get(day.key) ?? [] as sugg (sugg.task_id)}
            <button
              class="agenda-item-pill chip-ghost"
              title={sugg.rationale || $t('calendar.planAcceptHint')}
              onclick={(e) => {
                e.stopPropagation();
                onAcceptSuggestion(sugg);
              }}
            >
              <Sparkles size={9} class="lock-icon" />
              <span class="chip-time caption">{sugg.start_time}</span>
              <span class="pill-title">{taskTitle(sugg.task_id)}</span>
            </button>
          {/each}
        {/if}
      </div>
    </div>
  {/each}
</div>

<style>
  .agenda-view {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding-right: 4px;
  }

  .agenda-day-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface-2, rgba(255, 255, 255, 0.02));
    cursor: pointer;
    transition: all var(--t-fast) ease;
  }

  .agenda-day-row:hover {
    background: var(--hover);
  }

  .agenda-day-row.today {
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 10%, transparent);
  }

  .agenda-day-row.selected {
    border-color: var(--xp);
    box-shadow: 0 0 0 1px var(--xp);
  }

  .agenda-date-badge {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-width: 56px;
    padding: 4px;
    border-radius: calc(var(--r) * 0.6);
    background: var(--surface);
    border: 1px solid var(--border);
    flex-shrink: 0;
    gap: 2px;
  }

  .agenda-date-badge .day-num {
    font-size: 15px;
    font-weight: 700;
    line-height: 1;
  }

  .agenda-date-badge .caption {
    font-size: 10px;
    text-transform: capitalize;
  }

  .agenda-day-items {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    flex: 1;
    min-height: 28px;
  }

  .empty-agenda-day {
    font-style: italic;
    opacity: 0.5;
  }

  .agenda-item-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 8px;
    border-radius: 999px;
    background: var(--surface);
    border: 1px solid var(--border);
    font-size: 11px;
    max-width: 260px;
    cursor: pointer;
    color: var(--text-primary);
  }

  .agenda-item-pill.done {
    opacity: 0.55;
    text-decoration: line-through;
  }

  .pill-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .chip-time {
    font-size: 9px;
    opacity: 0.75;
    flex-shrink: 0;
  }

  .lock-icon,
  .recur-icon {
    flex-shrink: 0;
    opacity: 0.6;
  }

  .priority-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
    background: currentColor;
  }

  .prio-low {
    color: var(--text-muted);
  }
  .prio-medium {
    color: var(--accent);
  }
  .prio-high {
    color: #e08c3a;
  }
  .prio-urgent {
    color: #d9534f;
  }

  .chip-ghost {
    border: 1px dashed var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    color: var(--accent);
  }
</style>
