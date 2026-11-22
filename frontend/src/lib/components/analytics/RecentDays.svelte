<script lang="ts">
  import History from 'lucide-svelte/icons/history';
  import ChartCard from './ChartCard.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { parseLocalDate } from '$lib/utils/date';
  import { locale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';

  // Recent active days feed (#1499): the latest days with activity, newest
  // first. The number of rows adapts to the tile height so nothing scrolls.
  type DayRow = AnalyticsOverview['daily_activity'][number];

  const ROW_H = 30;

  let { activity }: { activity?: DayRow[] } = $props();

  let bodyH = $state(0);
  let limit = $derived(Math.max(2, Math.floor(bodyH / ROW_H)));

  let rows = $derived(
    (activity ?? [])
      .filter((d) => d.xp !== 0 || d.events > 0)
      .slice(-limit)
      .reverse()
  );
  let max = $derived(Math.max(1, ...rows.map((r) => Math.abs(r.xp))));
  let dateFmt = $derived(
    new Intl.DateTimeFormat($locale, { weekday: 'short', day: 'numeric', month: 'short' })
  );
  let today = $derived(new Date().toDateString());
</script>

<ChartCard title={$t('analyticsPage.recent.title')}>
  {#snippet icon()}<History size={13} />{/snippet}

  <div class="rd-body" bind:clientHeight={bodyH}>
    {#if rows.length === 0}
      <div class="chart-empty"><span>{$t('analyticsPage.weekday.empty')}</span></div>
    {:else}
      <div class="rd-list">
        {#each rows as day, i (day.date)}
          {@const d = parseLocalDate(day.date)}
          <div class="rd-row" class:negative={day.xp < 0} style:--i={i}>
            <span class="rd-date">
              {dateFmt.format(d)}
              {#if d.toDateString() === today}<span class="rd-today">{$t('analyticsPage.recent.today')}</span>{/if}
            </span>
            <div class="rd-track">
              <div class="rd-fill" style:width="{Math.max(3, (Math.abs(day.xp) / max) * 100)}%"></div>
            </div>
            <span class="rd-xp mono">{day.xp > 0 ? '+' : ''}{day.xp.toLocaleString()}</span>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</ChartCard>

<style>
  .rd-body {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .rd-list {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: hidden;
  }
  .rd-row {
    flex: 1;
    max-height: 40px;
    display: flex;
    align-items: center;
    gap: var(--s3);
    animation: rd-in 0.4s ease both;
    animation-delay: calc(var(--i) * 40ms);
  }
  .rd-date {
    width: 118px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10.5px;
    color: var(--text-secondary);
    text-transform: capitalize;
    white-space: nowrap;
  }
  .rd-today {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 0 5px;
    border-radius: var(--r-sm);
    color: var(--xp);
    border: 1px solid var(--xp);
  }
  .rd-track {
    flex: 1;
    height: 6px;
    border-radius: 3px;
    background: color-mix(in srgb, var(--text-primary) 6%, transparent);
    overflow: hidden;
  }
  .rd-fill {
    height: 100%;
    border-radius: 3px;
    background: color-mix(in srgb, var(--xp) 60%, transparent);
  }
  .rd-row.negative .rd-fill {
    background: color-mix(in srgb, var(--error) 70%, transparent);
  }
  .rd-row.negative .rd-xp {
    color: var(--error);
  }
  .rd-xp {
    width: 64px;
    flex-shrink: 0;
    text-align: right;
    font-size: 11px;
    font-weight: 700;
    color: var(--text-primary);
  }
  .chart-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    font-size: 12px;
  }
  @keyframes rd-in {
    from {
      opacity: 0;
      transform: translateX(-6px);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .rd-row {
      animation: none;
    }
  }
</style>
