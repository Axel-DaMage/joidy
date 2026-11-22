<script lang="ts">
  import History from 'lucide-svelte/icons/history';
  import ChartCard from './ChartCard.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { parseLocalDate } from '$lib/utils/date';
  import { locale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';

  // Recent active days feed (#1499): the last days with any activity,
  // newest first — a compact auxiliary tile that always has content.
  type DayRow = AnalyticsOverview['daily_activity'][number];

  let { activity, limit = 8 }: { activity?: DayRow[]; limit?: number } = $props();

  let rows = $derived(
    (activity ?? [])
      .filter((d) => d.xp > 0 || d.events > 0)
      .slice(-limit)
      .reverse()
  );
  let max = $derived(Math.max(1, ...rows.map((r) => r.xp)));
  let dateFmt = $derived(
    new Intl.DateTimeFormat($locale, { weekday: 'short', day: 'numeric', month: 'short' })
  );
</script>

<ChartCard title={$t('goalsAnalytics.recent.title')}>
  {#snippet icon()}<History size={15} />{/snippet}

  {#if rows.length === 0}
    <div class="chart-empty"><span>{$t('goalsAnalytics.weekday.empty')}</span></div>
  {:else}
    <div class="rd-list">
      {#each rows as day (day.date)}
        <div class="rd-row">
          <span class="rd-date">{dateFmt.format(parseLocalDate(day.date))}</span>
          <div class="rd-track">
            <div
              class="rd-fill"
              class:negative={day.xp < 0}
              style:width="{Math.max(3, (Math.abs(day.xp) / max) * 100)}%"
            ></div>
          </div>
          <span class="rd-xp mono" class:negative={day.xp < 0}>{day.xp.toLocaleString()} XP</span>
        </div>
      {/each}
    </div>
  {/if}
</ChartCard>

<style>
  .rd-list {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-evenly;
    overflow-y: auto;
  }
  .rd-row {
    display: flex;
    align-items: center;
    gap: var(--s3);
    padding: 3px 0;
  }
  .rd-date {
    width: 110px;
    flex-shrink: 0;
    font-size: 10px;
    color: var(--text-secondary);
    text-transform: capitalize;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .rd-track {
    flex: 1;
    height: 6px;
    border-radius: 3px;
    background: color-mix(in srgb, var(--text-primary) 7%, transparent);
    overflow: hidden;
  }
  .rd-fill {
    height: 100%;
    border-radius: 3px;
    background: color-mix(in srgb, var(--xp) 75%, transparent);
  }
  .rd-fill.negative {
    background: color-mix(in srgb, var(--danger, #e5534b) 75%, transparent);
  }
  .rd-xp.negative {
    color: var(--danger, #e5534b);
  }
  .rd-xp {
    width: 74px;
    flex-shrink: 0;
    text-align: right;
    font-size: 10px;
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
    min-height: 80px;
  }
</style>
