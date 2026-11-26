<script lang="ts">
  // GoalStatsRail — vertical KPI rail for the goals editor tab. Mirrors the
  // analytics dashboard rail (.ad-rail): a hero number with a completion meter
  // plus compact KPI rows. All values are derived client-side from the goals
  // list — no extra requests.
  import Target from 'lucide-svelte/icons/target';
  import CheckCircle2 from 'lucide-svelte/icons/check-circle-2';
  import Pause from 'lucide-svelte/icons/pause';
  import Pin from 'lucide-svelte/icons/pin';
  import CalendarCheck from 'lucide-svelte/icons/calendar-check';
  import { t } from 'svelte-i18n';

  interface Props {
    /** Goals in state ACTIVE. */
    active: number;
    /** Goals completed (state COMPLETED or is_completed). */
    completed: number;
    /** Goals in state PAUSED. */
    paused: number;
    /** Pinned goal count. */
    pinned: number;
    /** Actionable goals assigned for today. */
    today: number;
    /** Managed goals total (excludes INBOX and CANCELLED). */
    total: number;
  }

  let { active, completed, paused, pinned, today, total }: Props = $props();

  let doneShare = $derived(total > 0 ? Math.round((completed / total) * 100) : 0);
</script>

<aside class="gsr" aria-label={$t('goalsPage.editorRail.title')}>
  <div class="gsr-header">
    <span class="gsr-title">
      <Target size={11} />
      {$t('goalsPage.editorRail.title')}
    </span>
  </div>

  <div class="gsr-hero">
    <span class="gsr-hero-label">{$t('goalFilters.active')}</span>
    <span class="gsr-hero-val">{active}</span>
    <div class="gsr-meter"><i style:--p={doneShare / 100}></i></div>
    <span class="gsr-hero-sub"
      >{$t('goalsPage.editorRail.managed', { values: { count: total } })}</span
    >
  </div>

  <div class="gsr-kpis">
    <div class="gsr-kpi today">
      <div class="gsr-kpi-main">
        <span class="gsr-kpi-icon"><CalendarCheck size={14} /></span>
        <span class="gsr-kpi-val">{today}</span>
      </div>
      <span class="gsr-kpi-label">{$t('goalsPage.editorRail.today')}</span>
      <span class="gsr-kpi-sub">{$t('goalsPage.editorRail.todayHint')}</span>
    </div>

    <div class="gsr-kpi completed">
      <div class="gsr-kpi-main">
        <span class="gsr-kpi-icon"><CheckCircle2 size={14} /></span>
        <span class="gsr-kpi-val">{completed}</span>
      </div>
      <span class="gsr-kpi-label">{$t('goalsPage.editorRail.completed')}</span>
      <span class="gsr-kpi-sub"
        >{$t('goalsPage.editorRail.doneShare', { values: { pct: doneShare } })}</span
      >
    </div>

    <div class="gsr-kpi paused">
      <div class="gsr-kpi-main">
        <span class="gsr-kpi-icon"><Pause size={14} /></span>
        <span class="gsr-kpi-val">{paused}</span>
      </div>
      <span class="gsr-kpi-label">{$t('goalsPage.editorRail.paused')}</span>
      <span class="gsr-kpi-sub"></span>
    </div>

    <div class="gsr-kpi pinned">
      <div class="gsr-kpi-main">
        <span class="gsr-kpi-icon"><Pin size={14} /></span>
        <span class="gsr-kpi-val">{pinned}</span>
      </div>
      <span class="gsr-kpi-label">{$t('goalsPage.editorRail.pinned')}</span>
      <span class="gsr-kpi-sub"></span>
    </div>
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
    min-height: 0;
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
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .gsr-kpi {
    flex: 1 1 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    min-width: 0;
    text-align: center;
  }
  .gsr-kpi + .gsr-kpi {
    border-top: 1px solid color-mix(in srgb, var(--border) 76%, transparent);
  }
  .gsr-kpi-main {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    min-width: 0;
  }
  .gsr-kpi-icon {
    display: flex;
    color: var(--text-muted);
    flex-shrink: 0;
  }
  .gsr-kpi.today .gsr-kpi-icon {
    color: var(--xp);
  }
  .gsr-kpi.completed .gsr-kpi-icon {
    color: var(--success);
  }
  .gsr-kpi.paused .gsr-kpi-icon {
    color: var(--warning, #f59e0b);
  }
  .gsr-kpi.pinned .gsr-kpi-icon {
    color: var(--link);
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
    max-width: 100%;
  }
  .gsr-kpi-val {
    font-size: 20px;
    font-weight: 700;
    font-family: var(--font-mono);
    line-height: 1.1;
    color: var(--text-primary);
    white-space: nowrap;
  }
  .gsr-kpi-sub {
    font-size: 10px;
    color: var(--text-muted);
    min-height: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }

  /* Short viewports: drop secondary lines instead of scrolling (ad-rail parity). */
  @media (max-height: 800px) {
    .gsr-kpi-sub {
      display: none;
    }
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
    .gsr-header {
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
      flex: 0 0 auto;
      border-top: none;
      border-left: 1px solid var(--border);
      padding-left: var(--s3);
      min-width: 64px;
    }
    .gsr-kpi + .gsr-kpi {
      border-top: none;
    }
    .gsr-kpi-val {
      font-size: 15px;
    }
    .gsr-kpi-sub {
      display: none;
    }
  }
</style>
