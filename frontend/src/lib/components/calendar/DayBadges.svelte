<script lang="ts">
  /**
   * Compact per-day intelligence badges (#1658): focus minutes, notes, XP,
   * goals completed, mood and streak — progressive disclosure: the cell shows
   * icons only, full values live in the day panel and in tooltips.
   */
  import type { CalendarDayMetrics } from '$lib/api';
  import { moodGlyph } from './types';
  import { t } from 'svelte-i18n';

  let {
    metrics,
    compact = true,
  }: {
    metrics: CalendarDayMetrics | undefined;
    compact?: boolean;
  } = $props();

  const hasAny = $derived(
    !!metrics &&
      (metrics.xp > 0 ||
        metrics.focus_minutes > 0 ||
        metrics.notes > 0 ||
        metrics.goals_completed > 0 ||
        metrics.mood_score !== null ||
        metrics.streak_day)
  );

  function focusLabel(minutes: number): string {
    if (minutes >= 60) {
      const h = Math.floor(minutes / 60);
      const m = minutes % 60;
      return m > 0 ? `${h}h${m}m` : `${h}h`;
    }
    return `${minutes}m`;
  }
</script>

{#if hasAny && metrics}
  <span
    class="day-badges"
    class:compact
    title={$t('calendar.metrics.tooltip', {
      values: {
        focus: focusLabel(metrics.focus_minutes),
        xp: metrics.xp,
        notes: metrics.notes,
      },
    })}
  >
    {#if metrics.focus_minutes > 0}
      <span class="badge badge-focus" aria-label={$t('calendar.metrics.focus')}>
        ⏱{focusLabel(metrics.focus_minutes)}
      </span>
    {/if}
    {#if metrics.notes > 0}
      <span class="badge badge-notes" aria-label={$t('calendar.metrics.notes')}>
        📝{metrics.notes}
      </span>
    {/if}
    {#if metrics.xp > 0}
      <span class="badge badge-xp" aria-label={$t('calendar.metrics.xp')}>
        ✦{metrics.xp}
      </span>
    {/if}
    {#if metrics.goals_completed > 0}
      <span class="badge badge-goals" aria-label={$t('calendar.metrics.goals')}>
        🎯{metrics.goals_completed}
      </span>
    {/if}
    {#if metrics.mood_score !== null}
      <span class="badge badge-mood" aria-label={$t('calendar.metrics.mood')}>
        {moodGlyph(metrics.mood_score)}
      </span>
    {/if}
    {#if metrics.streak_day}
      <span class="badge badge-streak" aria-label={$t('calendar.metrics.streak')}>🔥</span>
    {/if}
  </span>
{/if}

<style>
  .day-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 2px;
    align-items: center;
  }

  .day-badges.compact {
    max-width: 100%;
    overflow: hidden;
  }

  .badge {
    font-size: 8px;
    line-height: 1.3;
    padding: 0 3px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--text-muted) 14%, transparent);
    color: var(--text-muted);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  .badge-xp {
    color: var(--xp);
    background: color-mix(in srgb, var(--xp) 14%, transparent);
  }

  .badge-focus {
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 14%, transparent);
  }
</style>
