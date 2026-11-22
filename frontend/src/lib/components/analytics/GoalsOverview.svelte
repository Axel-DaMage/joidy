<script lang="ts">
  import Target from 'lucide-svelte/icons/target';
  import ChartCard from './ChartCard.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { t } from 'svelte-i18n';

  // Goals overview (#1499): lifecycle funnel (created → activated →
  // completed | abandoned) and per-temporality effectiveness. Effectiveness is
  // the success rate over *decided* goals (completed ÷ completed+failed);
  // temporalities with nothing decided yet fall back to average progress.
  type GoalsStats = AnalyticsOverview['goals'];

  let { goals }: { goals?: GoalsStats } = $props();

  const STAGE_COLORS: Record<string, string> = {
    created: 'var(--text-muted)',
    activated: 'var(--link)',
    completed: 'var(--success)',
    abandoned: 'var(--error)',
  };

  let funnel = $derived(goals?.funnel ?? []);
  let funnelMax = $derived(Math.max(1, ...funnel.map((s) => s.count)));
  let activatedCount = $derived(
    funnel.find((s) => s.stage === 'activated')?.count ?? funnel[0]?.count ?? 0
  );

  function stageLabel(stage: string): string {
    const key = `goalsAnalytics.goals.stages.${stage}`;
    const label = $t(key);
    return label === key ? stage.replace(/_/g, ' ') : label;
  }

  /**
   * Share of the reference stage. `abandoned` branches off `activated` (a goal
   * is either completed or abandoned), so both are measured against the
   * activated count; `activated` is measured against created.
   */
  function shareOf(index: number): number | null {
    if (index <= 0 || funnel.length === 0) return null;
    const stage = funnel[index].stage;
    const denom =
      stage === 'completed' || stage === 'abandoned'
        ? activatedCount
        : (funnel[index - 1]?.count ?? 0);
    return denom > 0 ? Math.round((funnel[index].count / denom) * 100) : null;
  }

  function temporalityLabel(temp: string): string {
    const key = `goalsAnalytics.goals.temporalities.${temp}`;
    const label = $t(key);
    return label === key ? temp : label;
  }

  let temporality = $derived(goals?.by_temporality ?? []);
</script>

<ChartCard title={$t('goalsAnalytics.slides.goals')}>
  {#snippet icon()}<Target size={13} />{/snippet}
  {#if funnel.length === 0 && temporality.length === 0}
    <div class="chart-empty">
      <Target size={22} style="opacity:0.25" />
      <span>{$t('goalsAnalytics.goals.empty')}</span>
    </div>
  {:else}
    <div class="go-layout">
      <div class="go-col">
        <span class="go-col-title">{$t('goalsAnalytics.goals.funnelTitle')}</span>
        <div class="go-rows">
          {#each funnel as stage, i (stage.stage)}
            {@const share = shareOf(i)}
            <div class="go-row" style:--i={i}>
              <span class="go-name">{stageLabel(stage.stage)}</span>
              <div class="go-track">
                <div
                  class="go-fill"
                  style="width: {Math.max(2, (stage.count / funnelMax) * 100)}%; background: {STAGE_COLORS[
                    stage.stage
                  ] ?? 'var(--xp)'};"
                ></div>
              </div>
              <span class="go-val mono">{stage.count}</span>
              <span class="go-share mono"
                >{#if share !== null}{share}%{/if}</span
              >
            </div>
          {/each}
        </div>
      </div>

      <div class="go-sep"></div>

      <div class="go-col">
        <span class="go-col-title">{$t('goalsAnalytics.goals.temporalityTitle')}</span>
        <div class="go-rows">
          {#each temporality as temp, i (temp.temporality)}
            {@const decided = temp.completed + temp.failed}
            <div class="go-row" style:--i={i}>
              <span class="go-name">{temporalityLabel(temp.temporality)}</span>
              <div class="go-track go-track-split">
                {#if decided > 0}
                  <div
                    class="go-fill"
                    style="width: {(temp.completed / decided) * 100}%; background: var(--success);"
                  ></div>
                  <div
                    class="go-fill"
                    style="width: {(temp.failed / decided) * 100}%; background: var(--error);"
                  ></div>
                {:else}
                  <div
                    class="go-fill"
                    style="width: {Math.max(2, Math.min(100, temp.avg_progress))}%; background: var(--xp);"
                  ></div>
                {/if}
              </div>
              <span class="go-val mono">{temp.completed}<span class="go-of">/{temp.total}</span></span>
              <span class="go-share mono">
                {#if decided > 0}{Math.round((temp.completed / decided) * 100)}%{:else}{Math.round(
                    temp.avg_progress
                  )}%{/if}
              </span>
            </div>
          {/each}
        </div>
        <span class="go-note">{$t('goalsAnalytics.goals.rateNote')}</span>
      </div>
    </div>
  {/if}
</ChartCard>

<style>
  .go-layout {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(0, 1fr) 1px minmax(0, 1fr);
    gap: var(--s5);
  }
  .go-sep {
    background: var(--border);
  }
  .go-col {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    min-width: 0;
    min-height: 0;
  }
  .go-col-title {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .go-rows {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-around;
  }
  .go-row {
    flex: 1;
    display: flex;
    align-items: center;
    gap: var(--s3);
    border-top: 1px solid var(--border);
    animation: go-in 0.45s ease both;
    animation-delay: calc(var(--i) * 70ms);
  }
  .go-name {
    width: 86px;
    flex-shrink: 0;
    font-size: 10.5px;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .go-track {
    flex: 1;
    height: 10px;
    border-radius: 3px;
    background: color-mix(in srgb, var(--text-primary) 6%, transparent);
    overflow: hidden;
  }
  .go-track-split {
    display: flex;
  }
  .go-fill {
    height: 100%;
    transition: width 0.5s ease;
    transform-origin: left;
    animation: go-grow 0.8s cubic-bezier(0.2, 0.7, 0.2, 1) both;
  }
  .go-val {
    min-width: 34px;
    text-align: right;
    font-size: 12px;
    font-weight: 700;
    color: var(--text-primary);
  }
  .go-of {
    color: var(--text-muted);
    font-weight: 400;
    font-size: 10px;
  }
  .go-share {
    width: 36px;
    text-align: right;
    font-size: 10px;
    color: var(--text-muted);
  }
  .go-note {
    font-size: 9.5px;
    line-height: 1.4;
    color: var(--text-muted);
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
  }
  @keyframes go-in {
    from {
      opacity: 0;
      transform: translateX(-6px);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
  @keyframes go-grow {
    from {
      transform: scaleX(0);
    }
    to {
      transform: scaleX(1);
    }
  }
  @media (max-width: 700px) {
    .go-layout {
      grid-template-columns: 1fr;
    }
    .go-sep {
      display: none;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .go-row,
    .go-fill {
      animation: none;
    }
  }
</style>
