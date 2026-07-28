<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';

  let weeklyData: { date: string; notes_created: number; xp_events: number }[] = [];
  let xpEventsWeek = 0;
  let loading = true;

  function getWeekBounds(): { start: Date; end: Date } {
    const now = new Date();
    const day = now.getDay();
    const diff = day === 0 ? 6 : day - 1;
    const monday = new Date(now);
    monday.setDate(now.getDate() - diff);
    monday.setHours(0, 0, 0, 0);
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    sunday.setHours(23, 59, 59, 999);
    return { start: monday, end: sunday };
  }

  function isSameDay(a: Date, b: Date): boolean {
    return a.getFullYear() === b.getFullYear()
      && a.getMonth() === b.getMonth()
      && a.getDate() === b.getDate();
  }

  $: dayLabels = ['L', 'M', 'X', 'J', 'V', 'S', 'D'];

  $: weekDays = (() => {
    const { start } = getWeekBounds();
    const days: { label: string; active: boolean; date: Date }[] = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      const active = weeklyData.some(w => {
        const wd = new Date(w.date + 'T00:00:00');
        return isSameDay(wd, d) && (w.notes_created > 0 || w.xp_events > 0);
      });
      days.push({ label: dayLabels[i], active, date: d });
    }
    return days;
  })();

  $: notesThisWeek = weeklyData
    .filter(w => {
      const wd = new Date(w.date + 'T00:00:00');
      const { start, end } = getWeekBounds();
      return wd >= start && wd <= end;
    })
    .reduce((sum, d) => sum + d.notes_created, 0);

  $: activeDays = weekDays.filter(d => d.active).length;

  onMount(async () => {
    try {
      const [activity, system] = await Promise.all([
        api.stats.activity(30),
        api.stats.system(),
      ]);
      weeklyData = activity.days;
      xpEventsWeek = system.xp_events_week;
    } catch {
      weeklyData = [];
    } finally {
      loading = false;
    }
  });
</script>

<div class="activity-progress">
  {#if loading}
    <div class="loading-pulse" />
  {:else}
    <div class="week-strip">
      {#each weekDays as day}
        <div
          class="day-cell"
          class:active={day.active}
          title={day.date.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'short' })}
        >
          <span class="day-label">{day.label}</span>
        </div>
      {/each}
    </div>

    <div class="week-stats">
      <div class="stat-item">
        <span class="stat-value">{activeDays}/7</span>
        <span class="stat-label">días activos</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{notesThisWeek}</span>
        <span class="stat-label">notas</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{xpEventsWeek}</span>
        <span class="stat-label">eventos XP</span>
      </div>
    </div>
  {/if}
</div>

<style>
  .activity-progress {
    width: 100%;
    padding: 8px 0;
  }

  .loading-pulse {
    height: 48px;
    background: var(--border-light);
    border-radius: var(--r);
    animation: pulse 1.5s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 0.8; }
  }

  .week-strip {
    display: flex;
    gap: 4px;
    justify-content: center;
    margin-bottom: 10px;
  }

  .day-cell {
    width: 28px;
    height: 32px;
    border-radius: 4px;
    background: var(--border-light);
    display: flex;
    align-items: flex-end;
    justify-content: center;
    transition: background var(--t-fast);
  }

  .day-cell.active {
    background: var(--accent);
  }

  .day-label {
    font-size: 9px;
    color: var(--text-muted);
    padding-bottom: 3px;
  }

  .day-cell.active .day-label {
    color: var(--bg);
  }

  .week-stats {
    display: flex;
    justify-content: space-around;
  }

  .stat-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
  }

  .stat-value {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .stat-label {
    font-size: 9px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
</style>
