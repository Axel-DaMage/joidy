<script lang="ts">
  import Target from 'lucide-svelte/icons/target';
  import ArrowDown from 'lucide-svelte/icons/arrow-down';
  import ChartCard from './ChartCard.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { t } from 'svelte-i18n';

  // Goals overview (#1499): conversion funnel (created → activated →
  // completed | abandoned), per-temporality effectiveness bars, and a footer
  // with goal-state chips + habit check-in stats.
  type GoalsStats = AnalyticsOverview['goals'];
  type StreaksStats = AnalyticsOverview['streaks'];

  let { goals, streaks }: { goals?: GoalsStats; streaks?: StreaksStats } = $props();

  const STAGE_COLORS: Record<string, string> = {
    created: 'var(--text-muted)',
    activated: 'var(--link)',
    completed: 'var(--success)',
    abandoned: 'var(--error)',
  };

  const STATE_COLORS: Record<string, string> = {
    ACTIVE: 'var(--link)',
    INBOX: 'var(--text-muted)',
    COMPLETED: 'var(--success)',
    FAILED: 'var(--error)',
    PAUSED: 'var(--xp)',
    CANCELLED: 'var(--text-muted)',
  };

  let funnel = $derived(goals?.funnel ?? []);
  let funnelMax = $derived(Math.max(1, ...funnel.map((s) => s.count)));
  let activatedCount = $derived(
    funnel.find((s) => s.stage === 'activated')?.count ?? funnel[0]?.count ?? 0
  );

  function stageLabel(stage: string): string {
    const key = `goalsAnalytics.goals.stages.${stage}`;
    const label = $t(key);
    // svelte-i18n echoes the key back when it is missing — fall back to the
    // humanized stage name instead of leaking the raw key.
    return label === key ? stage.replace(/_/g, ' ') : label;
  }

  /**
   * Conversion into a stage. `abandoned` branches off `activated` (a goal is
   * either completed or abandoned), so its denominator is the activated
   * count, not the completed count.
   */
  function conversionInto(index: number): number | null {
    if (index <= 0 || funnel.length === 0) return null;
    const stage = funnel[index].stage;
    const denom =
      stage === 'abandoned' ? activatedCount : (funnel[index - 1]?.count ?? 0);
    if (denom <= 0) return null;
    return Math.round((funnel[index].count / denom) * 100);
  }

  function temporalityLabel(temp: string): string {
    const key = `goalsAnalytics.goals.temporalities.${temp}`;
    const label = $t(key);
    return label === key ? temp : label;
  }

  let temporality = $derived(goals?.by_temporality ?? []);
  let stateChips = $derived(Object.entries(goals?.by_state ?? {}).filter(([, n]) => n > 0));

  function stateLabel(state: string): string {
    const key = `goalsAnalytics.goals.states.${state}`;
    const label = $t(key);
    return label === key ? state.toLowerCase() : label;
  }
</script>

<ChartCard title={$t('goalsAnalytics.slides.goals')}>
  {#snippet icon()}<Target size={15} />{/snippet}
  {#if funnel.length === 0 && temporality.length === 0}
    <div class="chart-empty">
      <Target size={22} style="opacity:0.25" />
      <span>{$t('goalsAnalytics.goals.empty')}</span>
    </div>
  {:else}
    <div class="go-layout">
      <div class="go-col">
        <span class="go-col-title">{$t('goalsAnalytics.goals.funnelTitle')}</span>
        <div class="go-funnel">
          {#each funnel as stage, i (stage.stage)}
            {@const conv = conversionInto(i)}
            {#if conv !== null}
              <div class="go-conv">
                <ArrowDown size={10} />
                <span
                  >{$t('goalsAnalytics.goals.conversion', { values: { pct: conv } })}</span
                >
              </div>
            {/if}
            <div class="go-stage">
              <div class="go-stage-info">
                <span class="go-stage-name">{stageLabel(stage.stage)}</span>
                <span class="go-stage-val" style="color: {STAGE_COLORS[stage.stage] ?? 'var(--text-primary)'}"
                  >{stage.count}</span
                >
              </div>
              <div class="go-stage-track">
                <div
                  class="go-stage-bar"
                  style="width: {(stage.count / funnelMax) * 100}%; background: {STAGE_COLORS[
                    stage.stage
                  ] ?? 'var(--xp)'};"
                ></div>
              </div>
            </div>
          {/each}
        </div>
      </div>

      <div class="go-col">
        <span class="go-col-title">{$t('goalsAnalytics.goals.temporalityTitle')}</span>
        <div class="go-temps">
          {#each temporality as temp (temp.temporality)}
            {@const decided = temp.completed + temp.failed}
            <div class="go-temp">
              <div class="go-temp-info">
                <span class="go-temp-name">{temporalityLabel(temp.temporality)}</span>
                <span class="go-temp-stats">
                  <span class="text-success">{temp.completed} ✓</span>
                  <span class="text-error">{temp.failed} ✗</span>
                  <span class="go-temp-total">/ {temp.total}</span>
                </span>
              </div>
              <div class="go-temp-track">
                {#if decided > 0}
                  <div
                    class="go-temp-bar"
                    style="width: {(temp.completed / decided) * 100}%; background: var(--success);"
                  ></div>
                  <div
                    class="go-temp-bar"
                    style="width: {(temp.failed / decided) * 100}%; background: var(--error);"
                  ></div>
                {:else}
                  <div
                    class="go-temp-bar"
                    style="width: {Math.min(100, temp.avg_progress)}%; background: var(--xp);"
                  ></div>
                {/if}
              </div>
              <span class="go-temp-avg"
                >{$t('goalsAnalytics.goals.avgProgress', {
                  values: { pct: Math.round(temp.avg_progress) },
                })}</span
              >
            </div>
          {/each}
        </div>
      </div>
    </div>

    {#if stateChips.length > 0 || streaks}
      <div class="go-footer">
        {#if stateChips.length > 0}
          <div class="go-footer-group">
            <span class="go-col-title">{$t('goalsAnalytics.goals.statesTitle')}</span>
            <div class="go-chips">
              {#each stateChips as [state, count] (state)}
                <span class="go-chip">
                  <span
                    class="go-chip-dot"
                    style="background: {STATE_COLORS[state] ?? 'var(--text-muted)'}"
                  ></span
                  >{stateLabel(state)} <b>{count}</b>
                </span>
              {/each}
            </div>
          </div>
        {/if}
        {#if streaks}
          <div class="go-footer-group">
            <span class="go-col-title">{$t('goalsAnalytics.goals.habitsTitle')}</span>
            <div class="go-chips">
              <span class="go-chip"
                >{$t('goalsAnalytics.goals.checkinRate', {
                  values: { pct: streaks.checkin_rate_30d },
                })}</span
              >
              <span class="go-chip"
                >{$t('goalsAnalytics.goals.activeStreaks', {
                  values: { count: streaks.active_streaks },
                })}</span
              >
              <span class="go-chip"
                >{$t('goalsAnalytics.goals.totalCheckins', {
                  values: { count: streaks.total_checkins },
                })}</span
              >
            </div>
          </div>
        {/if}
      </div>
    {/if}
  {/if}
</ChartCard>

<style>
  .go-layout {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s5);
    align-items: start;
  }
  .go-col {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    min-width: 0;
  }
  .go-col-title {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .go-funnel {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .go-stage {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .go-stage-info {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  .go-stage-name {
    font-size: 10px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .go-stage-val {
    font-size: 12px;
    font-weight: 700;
    font-family: var(--font-mono);
  }
  .go-stage-track {
    height: 8px;
    background: color-mix(in srgb, var(--text-primary) 6%, transparent);
    border-radius: 4px;
    overflow: hidden;
  }
  .go-stage-bar {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s ease;
  }
  .go-conv {
    display: flex;
    align-items: center;
    gap: 4px;
    padding-left: var(--s3);
    color: var(--text-muted);
    font-size: 9px;
    font-family: var(--font-mono);
  }
  .go-temps {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
  }
  .go-temp {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .go-temp-info {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 10px;
  }
  .go-temp-name {
    font-weight: 600;
    color: var(--text-secondary);
  }
  .go-temp-stats {
    font-family: var(--font-mono);
    font-size: 10px;
    display: flex;
    gap: 5px;
  }
  .go-temp-total {
    color: var(--text-muted);
  }
  .go-temp-track {
    height: 8px;
    background: color-mix(in srgb, var(--text-primary) 6%, transparent);
    border-radius: 4px;
    overflow: hidden;
    display: flex;
  }
  .go-temp-bar {
    height: 100%;
    transition: width 0.5s ease;
  }
  .go-temp-avg {
    font-size: 9px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .go-footer {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: var(--s4);
    flex-wrap: wrap;
    border-top: 1px solid var(--border);
    padding-top: var(--s3);
    margin-top: var(--s3);
  }
  .go-footer-group {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    min-width: 0;
  }
  .go-chips {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .go-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 9px;
    border: 1px solid var(--border);
    border-radius: 999px;
    font-size: 9px;
    font-family: var(--font-mono);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .go-chip b {
    color: var(--text-primary);
  }
  .go-chip-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .chart-empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: var(--text-muted);
    font-size: 12px;
    text-align: center;
    min-height: 160px;
  }
  @media (max-width: 700px) {
    .go-layout {
      grid-template-columns: 1fr;
      gap: var(--s4);
    }
  }
</style>
