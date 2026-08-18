<script lang="ts">
  import type { StreakStats } from '$lib/api';
  import { ChartNoAxesColumn, Calendar } from 'lucide-svelte';
  import { t } from 'svelte-i18n';

  export let stats: StreakStats | null = null;
</script>

{#if stats}
  <div class="stats-panel">
    <div class="stats-header">
      <ChartNoAxesColumn size={12} />
      <span>RESUMEN GLOBAL</span>
    </div>

    <div class="stats-grid">
      <div class="stat-block">
        <span class="stat-val mono">{stats.total_active}</span>
        <span class="stat-lbl">{$t('streakStats.active')}</span>
      </div>
      <div class="stat-block">
        <span class="stat-val mono">{stats.total_archived}</span>
        <span class="stat-lbl">{$t('streakStats.archived')}</span>
      </div>
      <div class="stat-block">
        <span class="stat-val mono">{stats.longest_ever}</span>
        <span class="stat-lbl">{$t('streakStats.record')}</span>
      </div>
    </div>

    {#if stats.longest_name}
      <div class="longest-info">
        <span class="longest-label">{$t('streakStats.longestStreak')}</span>
        <span class="longest-name mono">{stats.longest_name}</span>
        <span class="longest-days">{stats.longest_ever} días</span>
      </div>
    {/if}

    <div class="tracker-row">
      <Calendar size={11} />
      <span>{stats.days_tracked} días trackeados</span>
      <span class="sep">·</span>
      <span>{stats.total_checkins} check-ins totales</span>
    </div>
  </div>
{/if}

<style>
  .stats-panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--surface);
  }

  .stats-header {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.1em;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }

  @media (max-width: 480px) {
    .stats-grid {
      grid-template-columns: repeat(3, 1fr);
      gap: var(--s1);
    }
    .stat-block {
      padding: var(--s1_5) var(--s0_5);
    }
    .stat-val {
      font-size: 15px;
    }
  }

  @media (max-width: 360px) {
    .stats-grid {
      grid-template-columns: 1fr;
      gap: var(--s1_5);
    }
  }

  .stat-block {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 8px 4px;
    background: var(--elevated);
    border-radius: 6px;
    border: 1px solid var(--border-light);
  }

  .stat-val {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1;
  }

  .stat-lbl {
    font-size: 9px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .longest-info {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    padding: 8px 10px;
    background: var(--elevated);
    border-radius: 4px;
    border: 1px solid var(--border-light);
  }

  .longest-label {
    color: var(--text-muted);
  }
  .longest-name {
    color: var(--text-primary);
    font-size: 12px;
  }
  .longest-days {
    color: var(--xp);
    margin-left: auto;
    font-size: 11px;
    font-weight: 600;
  }

  .tracker-row {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    color: var(--text-muted);
  }

  .sep {
    opacity: 0.3;
  }
</style>
