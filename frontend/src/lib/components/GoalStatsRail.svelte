<script lang="ts">
  // GoalStatsRail — compact KPI rail for the goals editor tab, mirroring the
  // analytics dashboard rail (.ad-rail): an actionable hero (today's progress
  // X/Y with a real completion meter) plus slim horizontal KPI rows for the
  // state inventory. All values are derived client-side from the goals list —
  // no extra requests.
  import Target from 'lucide-svelte/icons/target';
  import CheckCircle2 from 'lucide-svelte/icons/check-circle-2';
  import Pause from 'lucide-svelte/icons/pause';
  import CalendarCheck from 'lucide-svelte/icons/calendar-check';
  import { t } from 'svelte-i18n';

  interface Props {
    /** Goals in state ACTIVE. */
    active: number;
    /** Goals completed (state COMPLETED or is_completed). */
    completed: number;
    /** Goals in state PAUSED. */
    paused: number;
    /** Managed goals assigned for today. */
    todayTotal: number;
    /** Of those, already completed today. */
    todayDone: number;
    /** Managed goals total (excludes INBOX and CANCELLED). */
    total: number;
  }

  let { active, completed, paused, todayTotal, todayDone, total }: Props = $props();

  let todayShare = $derived(todayTotal > 0 ? todayDone / todayTotal : 0);
</script>

<aside class="gsr" aria-label={$t('goalsPage.editorRail.title')}>
  <div class="gsr-header">
    <span class="gsr-title">
      <Target size={11} />
      {$t('goalsPage.editorRail.title')}
    </span>
  </div>

  <div class="gsr-hero">
    <span class="gsr-hero-label">{$t('goalsPage.editorRail.today')}</span>
    <span class="gsr-hero-val">
      {todayDone}<span class="gsr-hero-of">/{todayTotal}</span>
    </span>
    <div class="gsr-meter"><i style:--p={todayShare}></i></div>
    <span class="gsr-hero-sub">
      {#if todayTotal === 0}
        {$t('goalsPage.editorRail.noneToday')}
      {:else if todayDone === todayTotal}
        {$t('goalsPage.editorRail.dayComplete')}
      {:else}
        {$t('goalsPage.editorRail.pendingToday', { values: { count: todayTotal - todayDone } })}
      {/if}
    </span>
  </div>

  <div class="gsr-kpis">
    <div class="gsr-kpi active">
      <span class="gsr-kpi-icon"><Target size={14} /></span>
      <div class="gsr-kpi-txt">
        <span class="gsr-kpi-label">{$t('goalsPage.editorRail.active')}</span>
        <span class="gsr-kpi-val">{active}</span>
      </div>
    </div>

    <div class="gsr-kpi completed">
      <span class="gsr-kpi-icon"><CheckCircle2 size={14} /></span>
      <div class="gsr-kpi-txt">
        <span class="gsr-kpi-label">{$t('goalsPage.editorRail.completed')}</span>
        <span class="gsr-kpi-val">{completed}</span>
      </div>
    </div>

    <div class="gsr-kpi paused">
      <span class="gsr-kpi-icon"><Pause size={14} /></span>
      <div class="gsr-kpi-txt">
        <span class="gsr-kpi-label">{$t('goalsPage.editorRail.paused')}</span>
        <span class="gsr-kpi-val">{paused}</span>
      </div>
    </div>
  </div>

  <div class="gsr-foot">
    <CalendarCheck size={10} />
    {$t('goalsPage.editorRail.managed', { values: { count: total } })}
  </div>
</aside>

<style>
  .gsr {
    display: flex;
    flex-direction: column;
    width: 208px;
    flex-shrink: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3);
    overflow: hidden;
    align-self: flex-start;
  }

  .gsr-header {
    display: flex;
    justify-content: center;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .gsr-title {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    max-width: 100%;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: var(--text-muted);
    font-family: var(--font-mono);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .gsr-hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    flex-shrink: 0;
    text-align: center;
    padding: 14px 0 13px;
    border-bottom: 1px solid var(--border);
  }
  .gsr-hero-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .gsr-hero-val {
    font-size: 34px;
    font-weight: 700;
    line-height: 1;
    font-family: var(--font-mono);
    color: var(--text-primary);
  }
  .gsr-hero-of {
    font-size: 18px;
    color: var(--text-muted);
  }
  .gsr-meter {
    width: 100%;
    max-width: 132px;
    height: 4px;
    border-radius: 2px;
    background: color-mix(in srgb, var(--text-primary) 8%, transparent);
    overflow: hidden;
    margin-top: 4px;
  }
  .gsr-meter i {
    display: block;
    height: 100%;
    border-radius: 2px;
    background: var(--success);
    transform-origin: left;
    transform: scaleX(var(--p));
    transition: transform 0.6s ease;
  }
  .gsr-hero-sub {
    font-size: 10px;
    color: var(--text-muted);
    min-height: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }

  .gsr-kpis {
    display: flex;
    flex-direction: column;
  }
  .gsr-kpi {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 2px;
    min-width: 0;
  }
  .gsr-kpi + .gsr-kpi {
    border-top: 1px solid color-mix(in srgb, var(--border) 76%, transparent);
  }
  .gsr-kpi-icon {
    display: flex;
    color: var(--text-muted);
    flex-shrink: 0;
  }
  .gsr-kpi.active .gsr-kpi-icon {
    color: var(--xp);
  }
  .gsr-kpi.completed .gsr-kpi-icon {
    color: var(--success);
  }
  .gsr-kpi.paused .gsr-kpi-icon {
    color: var(--warning, #f59e0b);
  }
  .gsr-kpi-txt {
    display: flex;
    align-items: baseline;
    gap: 6px;
    min-width: 0;
    flex: 1;
  }
  .gsr-kpi-label {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-family: var(--font-mono);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
    min-width: 0;
  }
  .gsr-kpi-val {
    font-size: 16px;
    font-weight: 700;
    font-family: var(--font-mono);
    line-height: 1.1;
    color: var(--text-primary);
    white-space: nowrap;
  }
  .gsr-foot {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    padding-top: 9px;
    border-top: 1px solid var(--border);
    font-size: 9px;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    white-space: nowrap;
  }

  /* Mobile: collapse to a horizontal strip above the list. */
  @media (max-width: 900px) {
    .gsr {
      width: 100%;
      flex-direction: row;
      align-items: center;
      gap: var(--s3);
      overflow-x: auto;
      padding: var(--s2) var(--s3);
    }
    .gsr-header,
    .gsr-foot {
      display: none;
    }
    .gsr-hero {
      flex-direction: row;
      flex-shrink: 0;
      gap: var(--s2);
      text-align: left;
      padding: 0;
      border-bottom: none;
    }
    .gsr-hero-val {
      font-size: 22px;
    }
    .gsr-hero-of {
      font-size: 13px;
    }
    .gsr-meter {
      width: 56px;
      margin-top: 0;
    }
    .gsr-hero-sub {
      display: none;
    }
    .gsr-kpis {
      flex-direction: row;
      flex: 0 0 auto;
    }
    .gsr-kpi {
      border-top: none;
      border-left: 1px solid var(--border);
      padding: 0 0 0 var(--s3);
    }
    .gsr-kpi-val {
      font-size: 14px;
    }
  }
</style>
