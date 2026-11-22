<script lang="ts">
  import GitCompare from 'lucide-svelte/icons/git-compare';
  import ArrowUp from 'lucide-svelte/icons/arrow-up';
  import ArrowDown from 'lucide-svelte/icons/arrow-down';
  import Minus from 'lucide-svelte/icons/minus';
  import ChartCard from './ChartCard.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { t } from 'svelte-i18n';

  // Period-over-period tile (#1499): the current window against the equally
  // long window immediately before it, for XP, active days and XP per active
  // day. Deltas below ±5% read as "flat" so noise is not shown as a trend.
  type Summary = AnalyticsOverview['summary'];

  let { summary }: { summary?: Summary } = $props();

  interface Metric {
    key: string;
    now: number;
    prev: number;
    suffix?: string;
  }

  let metrics = $derived.by<Metric[]>(() => {
    const s = summary;
    if (!s) return [];
    const perDay = (xp: number, d: number) => (d > 0 ? Math.round(xp / d) : 0);
    return [
      { key: 'xp', now: s.window_xp, prev: s.prev_total_xp },
      { key: 'days', now: s.active_days, prev: s.prev_active_days },
      {
        key: 'perDay',
        now: perDay(s.window_xp, s.active_days),
        prev: perDay(s.prev_total_xp, s.prev_active_days),
      },
    ];
  });

  function delta(m: Metric): number | null {
    return m.prev > 0 ? Math.round(((m.now - m.prev) / m.prev) * 100) : null;
  }
  const dir = (d: number | null) => (d === null ? 'none' : d >= 5 ? 'up' : d <= -5 ? 'down' : 'flat');
</script>

<ChartCard title={$t('goalsAnalytics.compare.title')}>
  {#snippet icon()}<GitCompare size={13} />{/snippet}

  <div class="pc-list">
    {#each metrics as m, i (m.key)}
      {@const d = delta(m)}
      {@const top = Math.max(1, m.now, m.prev)}
      <div class="pc-row" style:--i={i}>
        <div class="pc-head">
          <span class="pc-name">{$t(`goalsAnalytics.compare.${m.key}`)}</span>
          <span class="pc-chip {dir(d)}">
            {#if d === null}
              {$t('goalsAnalytics.compare.noPrev')}
            {:else}
              {#if dir(d) === 'up'}<ArrowUp size={10} />{:else if dir(d) === 'down'}<ArrowDown size={10} />{:else}<Minus size={10} />{/if}
              {Math.abs(d)}%
            {/if}
          </span>
        </div>
        <div class="pc-bars">
          <div class="pc-line">
            <span class="pc-tag">{$t('goalsAnalytics.compare.now')}</span>
            <div class="pc-track"><div class="pc-fill now" style:width="{(m.now / top) * 100}%"></div></div>
            <span class="pc-val mono">{m.now.toLocaleString()}</span>
          </div>
          <div class="pc-line">
            <span class="pc-tag">{$t('goalsAnalytics.compare.before')}</span>
            <div class="pc-track"><div class="pc-fill prev" style:width="{(m.prev / top) * 100}%"></div></div>
            <span class="pc-val mono dim">{m.prev.toLocaleString()}</span>
          </div>
        </div>
      </div>
    {/each}
  </div>
</ChartCard>

<style>
  .pc-list {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-around;
    gap: var(--s2);
  }
  .pc-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
    animation: pc-in 0.45s ease both;
    animation-delay: calc(var(--i) * 80ms);
  }
  .pc-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s2);
  }
  .pc-name {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }
  .pc-chip {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: 10px;
    font-weight: 800;
    font-family: var(--font-mono);
    padding: 1px 7px;
    border-radius: var(--r-sm);
    color: var(--text-muted);
    border: 1px solid var(--border);
  }
  .pc-chip.up {
    color: var(--success);
    border-color: color-mix(in srgb, var(--success) 40%, var(--border));
  }
  .pc-chip.down {
    color: var(--error);
    border-color: color-mix(in srgb, var(--error) 40%, var(--border));
  }
  .pc-chip.none {
    font-weight: 600;
    font-size: 9px;
  }
  .pc-bars {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .pc-line {
    display: flex;
    align-items: center;
    gap: var(--s2);
  }
  .pc-tag {
    width: 44px;
    flex-shrink: 0;
    font-size: 9px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    text-transform: uppercase;
  }
  .pc-track {
    flex: 1;
    height: 6px;
    border-radius: 3px;
    background: color-mix(in srgb, var(--text-primary) 6%, transparent);
    overflow: hidden;
  }
  .pc-fill {
    height: 100%;
    border-radius: 3px;
    transform-origin: left;
    animation: pc-grow 0.8s cubic-bezier(0.2, 0.7, 0.2, 1) both;
  }
  .pc-fill.now {
    background: var(--xp);
  }
  .pc-fill.prev {
    background: color-mix(in srgb, var(--text-primary) 22%, transparent);
  }
  .pc-val {
    width: 58px;
    flex-shrink: 0;
    text-align: right;
    font-size: 11px;
    font-weight: 700;
    color: var(--text-primary);
  }
  .pc-val.dim {
    color: var(--text-muted);
    font-weight: 600;
  }
  @media (max-height: 820px) {
    .pc-row {
      gap: 3px;
    }
    .pc-bars {
      gap: 2px;
    }
    .pc-chip {
      padding: 0 6px;
    }
  }
  @keyframes pc-in {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
  @keyframes pc-grow {
    from {
      transform: scaleX(0);
    }
    to {
      transform: scaleX(1);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .pc-row,
    .pc-fill {
      animation: none;
    }
  }
</style>
