<script lang="ts">
  // GoalUpcoming — compact 7-day agenda that fills the rail column under
  // GoalStatsRail in the editor tab. Same visual language as the rail:
  // uppercase mono micro-labels, colored dots per goal. Clicking a day jumps
  // to the planning tab with that date selected.
  import CalendarRange from 'lucide-svelte/icons/calendar-range';
  import type { Goal } from '$lib/api';
  import { t } from 'svelte-i18n';

  interface DayEntry {
    goal: Goal;
    status: 'COMPLETED' | 'FAILED' | 'PENDING';
  }
  interface Day {
    iso: string;
    entries: DayEntry[];
  }

  interface Props {
    days: Day[];
    todayIso: string;
    getGoalColor: (goal: Goal) => string;
    onSelectDay: (iso: string) => void;
  }

  let { days, todayIso, getGoalColor, onSelectDay }: Props = $props();

  function dayLabel(iso: string): string {
    const d = new Date(iso + 'T12:00:00');
    const today = new Date(todayIso + 'T12:00:00');
    const diff = Math.round((d.getTime() - today.getTime()) / 86_400_000);
    if (diff === 0) return $t('goalsPage.todayBtn');
    return d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' });
  }

  function entryColor(entry: DayEntry): string {
    if (entry.status === 'COMPLETED') return 'var(--success)';
    if (entry.status === 'FAILED') return 'var(--error)';
    return getGoalColor(entry.goal);
  }

  let isEmpty = $derived(days.every((d) => d.entries.length === 0));
</script>

<div class="gup" aria-label={$t('goalsPage.editorRail.upcoming')}>
  <div class="gup-header">
    <span class="gup-title">
      <CalendarRange size={11} />
      {$t('goalsPage.editorRail.upcoming')}
    </span>
  </div>

  <div class="gup-list">
    {#if isEmpty}
      <span class="gup-empty">{$t('goalsPage.editorRail.nothingAhead')}</span>
    {:else}
      {#each days as day (day.iso)}
        {#if day.entries.length > 0}
          <button class="gup-day" onclick={() => onSelectDay(day.iso)}>
            <span class="gup-day-label" class:today={day.iso === todayIso}>{dayLabel(day.iso)}</span>
            {#each day.entries as entry (entry.goal.id)}
              <span class="gup-entry">
                <i style="background: {entryColor(entry)}"></i>
                <span class="gup-entry-title" class:done={entry.status === 'COMPLETED'}
                  >{entry.goal.title}</span
                >
              </span>
            {/each}
          </button>
        {/if}
      {/each}
    {/if}
  </div>
</div>

<style>
  .gup {
    display: flex;
    flex-direction: column;
    width: 208px;
    flex: 1;
    min-height: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3);
    overflow: hidden;
  }

  .gup-header {
    display: flex;
    justify-content: center;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .gup-title {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: var(--text-muted);
    font-family: var(--font-mono);
    white-space: nowrap;
  }

  .gup-list {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-top: 8px;
  }

  .gup-empty {
    font-size: 10px;
    color: var(--text-muted);
    text-align: center;
    padding: 12px 4px;
  }

  .gup-day {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 6px 8px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: transparent;
    cursor: pointer;
    text-align: left;
    flex-shrink: 0;
    transition:
      background var(--t-fast),
      border-color var(--t-fast);
  }
  .gup-day:hover {
    background: var(--surface-hover);
    border-color: var(--text-muted);
  }
  .gup-day-label {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .gup-day-label.today {
    color: var(--xp);
  }
  .gup-entry {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }
  .gup-entry i {
    width: 6px;
    height: 6px;
    border-radius: 999px;
    flex-shrink: 0;
  }
  .gup-entry-title {
    font-size: 11px;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }
  .gup-entry-title.done {
    color: var(--text-muted);
    text-decoration: line-through;
  }

  /* Mobile: the rail strip hides secondary panels. */
  @media (max-width: 900px) {
    .gup {
      display: none;
    }
  }
</style>
