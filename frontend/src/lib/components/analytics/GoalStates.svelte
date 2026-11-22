<script lang="ts">
  import Layers from 'lucide-svelte/icons/layers';
  import ChartCard from './ChartCard.svelte';
  import CountUp from './CountUp.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { t } from 'svelte-i18n';

  // Goal states tile (#1499): a stacked bar of every goal by state plus a
  // legend with counts and shares.
  type GoalsStats = AnalyticsOverview['goals'];

  let { goals }: { goals?: GoalsStats } = $props();

  const STATE_ORDER = ['ACTIVE', 'COMPLETED', 'INBOX', 'PAUSED', 'FAILED', 'CANCELLED'];
  const STATE_COLORS: Record<string, string> = {
    ACTIVE: 'var(--link)',
    COMPLETED: 'var(--success)',
    INBOX: 'var(--text-secondary)',
    PAUSED: 'var(--today)',
    FAILED: 'var(--error)',
    CANCELLED: 'var(--text-muted)',
  };

  const order = (s: string) => {
    const i = STATE_ORDER.indexOf(s);
    return i < 0 ? 99 : i;
  };

  let rows = $derived(
    Object.entries(goals?.by_state ?? {})
      .filter(([, n]) => n > 0)
      .sort((a, b) => order(a[0]) - order(b[0]))
  );
  let total = $derived(rows.reduce((a, [, n]) => a + n, 0));

  function stateLabel(state: string): string {
    const key = `analyticsPage.goals.states.${state}`;
    const label = $t(key);
    return label === key ? state.toLowerCase() : label;
  }
</script>

<ChartCard title={$t('analyticsPage.goals.statesTitle')}>
  {#snippet icon()}<Layers size={13} />{/snippet}

  {#if total === 0}
    <div class="chart-empty"><span>{$t('analyticsPage.goals.empty')}</span></div>
  {:else}
    <div class="gs-wrap"><div class="gs-body">
      <div class="gs-total">
        <span class="gs-big"><CountUp value={total} /></span>
        <span class="gs-cap">{$t('analyticsPage.goals.totalGoals')}</span>
      </div>
      <div class="gs-bar" role="img" aria-label={$t('analyticsPage.goals.statesTitle')}>
        {#each rows as [state, n], i (state)}
          <div
            class="gs-seg"
            style:flex-grow={n}
            style:background={STATE_COLORS[state] ?? 'var(--text-muted)'}
            style:--i={i}
            title="{stateLabel(state)} · {n}"
          ></div>
        {/each}
      </div>
      <div class="gs-legend">
        {#each rows as [state, n] (state)}
          <div class="gs-item">
            <span class="gs-dot" style:background={STATE_COLORS[state] ?? 'var(--text-muted)'}></span>
            <span class="gs-name">{stateLabel(state)}</span>
            <span class="gs-n mono">{n}</span>
            <span class="gs-pct mono">{Math.round((n / total) * 100)}%</span>
          </div>
        {/each}
      </div>
    </div></div>
  {/if}
</ChartCard>

<style>
  .gs-wrap {
    container-type: inline-size;
    flex: 1;
    min-height: 0;
    display: flex;
  }
  @container (max-width: 300px) {
    .gs-legend {
      grid-template-columns: minmax(0, 1fr);
    }
  }
  .gs-body {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-around;
    gap: var(--s2);
  }
  .gs-total {
    display: flex;
    align-items: baseline;
    gap: var(--s2);
  }
  .gs-big {
    font-size: 28px;
    font-weight: 700;
    font-family: var(--font-mono);
    line-height: 1;
    color: var(--text-primary);
  }
  .gs-cap {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .gs-bar {
    display: flex;
    gap: 2px;
    height: 10px;
    border-radius: var(--r-sm);
    overflow: hidden;
  }
  .gs-seg {
    flex-basis: 0;
    min-width: 4px;
    transform-origin: left;
    animation: gs-grow 0.7s cubic-bezier(0.2, 0.7, 0.2, 1) both;
    animation-delay: calc(var(--i) * 70ms);
  }
  .gs-legend {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px var(--s4);
  }
  .gs-item {
    display: flex;
    align-items: center;
    gap: 7px;
    min-width: 0;
    font-size: 11px;
  }
  .gs-dot {
    width: 9px;
    height: 9px;
    border-radius: 2px;
    flex-shrink: 0;
  }
  .gs-name {
    flex: 1;
    min-width: 0;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .gs-n {
    font-weight: 800;
    color: var(--text-primary);
  }
  .gs-pct {
    width: 32px;
    text-align: right;
    font-size: 10px;
    color: var(--text-muted);
  }
  .chart-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    font-size: 12px;
  }
  @keyframes gs-grow {
    from {
      transform: scaleX(0);
    }
    to {
      transform: scaleX(1);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .gs-seg {
      animation: none;
    }
  }
</style>
