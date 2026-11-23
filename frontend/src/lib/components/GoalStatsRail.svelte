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
  <div class="gsr-hero">
    <span class="gsr-hero-label">
      <Target size={11} />
      {$t('goalsPage.editorRail.active')}
    </span>
    <span class="gsr-hero-val">{active}</span>
    <div class="gsr-meter"><i style:--p={doneShare / 100}></i></div>
    <span class="gsr-hero-sub"
      >{$t('goalsPage.editorRail.managed', { values: { count: total } })}</span
    >
  </div>

  <div class="gsr-kpis">
    <div class="gsr-kpi">
      <span class="gsr-kpi-icon"><CheckCircle2 size={14} /></span>
      <div class="gsr-kpi-txt">
        <span class="gsr-kpi-label">{$t('goalsPage.editorRail.completed')}</span>
        <span class="gsr-kpi-val">{completed}</span>
        <span class="gsr-kpi-sub"
          >{$t('goalsPage.editorRail.doneShare', { values: { pct: doneShare } })}</span
        >
      </div>
    </div>
    <div class="gsr-kpi">
      <span class="gsr-kpi-icon"><Pause size={14} /></span>
      <div class="gsr-kpi-txt">
        <span class="gsr-kpi-label">{$t('goalsPage.editorRail.paused')}</span>
        <span class="gsr-kpi-val">{paused}</span>
        <span class="gsr-kpi-sub"></span>
      </div>
    </div>
    <div class="gsr-kpi">
      <span class="gsr-kpi-icon"><Pin size={14} /></span>
      <div class="gsr-kpi-txt">
        <span class="gsr-kpi-label">{$t('goalsPage.editorRail.pinned')}</span>
        <span class="gsr-kpi-val">{pinned}</span>
        <span class="gsr-kpi-sub"></span>
      </div>
    </div>
    <div class="gsr-kpi">
      <span class="gsr-kpi-icon"><CalendarCheck size={14} /></span>
      <div class="gsr-kpi-txt">
        <span class="gsr-kpi-label">{$t('goalsPage.editorRail.today')}</span>
        <span class="gsr-kpi-val">{today}</span>
        <span class="gsr-kpi-sub">{$t('goalsPage.editorRail.todayHint')}</span>
      </div>
    </div>
  </div>
</aside>

<style>
  .gsr {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    width: 208px;
    flex-shrink: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3) var(--s4);
    overflow: hidden;
    min-height: 0;
  }

  .gsr-hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
    text-align: center;
  }
  .gsr-hero-label {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .gsr-hero-val {
    font-size: 32px;
    font-weight: 700;
    line-height: 1.05;
    font-family: var(--font-mono);
    color: var(--text-primary);
  }
  .gsr-meter {
    width: 100%;
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
    align-items: center;
    gap: 10px;
    min-width: 0;
    border-top: 1px solid var(--border);
  }
  .gsr-kpi-icon {
    display: flex;
    color: var(--text-muted);
    flex-shrink: 0;
  }
  .gsr-kpi-txt {
    display: flex;
    flex-direction: column;
    gap: 2px;
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
  }
  .gsr-kpi-val {
    font-size: 19px;
    font-weight: 700;
    font-family: var(--font-mono);
    line-height: 1.15;
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
      gap: var(--s4);
      overflow-x: auto;
      padding: var(--s2) var(--s3);
    }
    .gsr-hero {
      flex-direction: row;
      flex-shrink: 0;
      gap: var(--s2);
      text-align: left;
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
      min-width: 0;
    }
    .gsr-kpi-val {
      font-size: 15px;
    }
    .gsr-kpi-sub {
      display: none;
    }
  }
</style>
