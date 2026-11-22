<script lang="ts">
  import ChartCard from './ChartCard.svelte';
  import Activity from 'lucide-svelte/icons/activity';
  import type { GithubSummary } from '$lib/api';
  import { t } from 'svelte-i18n';

  // GitHub "pulse": contribution calendar, merge stats and discussion threads.
  let { summary, loading = false }: { summary?: GithubSummary | null; loading?: boolean } = $props();

  const nf = new Intl.NumberFormat();
  const compact = (n: number) =>
    n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : String(n);

  function mergeLabel(hours: number | null | undefined): string {
    if (hours == null) return '—';
    if (hours < 1) return `${Math.max(1, Math.round(hours * 60))} min`;
    if (hours < 48) return `${hours.toFixed(1)} h`;
    return `${(hours / 24).toFixed(1)} d`;
  }

  function bestDayLabel(iso: string | undefined): string {
    if (!iso) return '';
    const d = new Date(iso + 'T12:00:00');
    return new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short' }).format(d);
  }

  type Stat = { value: string; label: string; hint?: string };
  let stats = $derived.by<Stat[]>(() => {
    const s = summary;
    if (!s) return [];
    const { prs, threads, calendar } = s;
    return [
      { value: nf.format(calendar.total), label: $t('analyticsPage.github.p.contributions') },
      { value: nf.format(calendar.active_days), label: $t('analyticsPage.github.p.activeDays') },
      {
        value: calendar.best_day ? nf.format(calendar.best_day.count) : '—',
        label: $t('analyticsPage.github.p.bestDay'),
        hint: calendar.best_day ? bestDayLabel(calendar.best_day.date) : undefined,
      },
      { value: `${calendar.current_streak}d`, label: $t('analyticsPage.github.p.currentStreak') },
      { value: `${calendar.longest_streak}d`, label: $t('analyticsPage.github.p.longestStreak') },
      { value: nf.format(prs.merged), label: $t('analyticsPage.github.p.prsMerged') },
      { value: mergeLabel(prs.median_merge_hours), label: $t('analyticsPage.github.p.medianMerge') },
      { value: `+${compact(prs.additions)}`, label: $t('analyticsPage.github.p.additions') },
      { value: `−${compact(prs.deletions)}`, label: $t('analyticsPage.github.p.deletions') },
      { value: nf.format(threads.commented), label: $t('analyticsPage.github.p.commented') },
      { value: nf.format(threads.issues_closed), label: $t('analyticsPage.github.p.issuesClosed') },
      { value: nf.format(threads.discussions), label: $t('analyticsPage.github.p.discussions') },
    ];
  });
</script>

<ChartCard title={$t('analyticsPage.github.pulseTitle')}>
  {#snippet icon()}<Activity size={13} />{/snippet}
  {#if loading}
    <div class="chart-empty"><span>{$t('analyticsPage.github.loadingShort')}</span></div>
  {:else if stats.length === 0}
    <div class="chart-empty"><span>{$t('analyticsPage.github.summaryNeedToken')}</span></div>
  {:else}
    <div class="gp-grid">
      {#each stats as st (st.label)}
        <div class="gp-stat">
          <span class="gp-value mono">{st.value}</span>
          <span class="gp-label"
            >{st.label}{#if st.hint}<span class="gp-hint"> · {st.hint}</span>{/if}</span
          >
        </div>
      {/each}
    </div>
    {#if summary?.prs.sampled}
      <span class="gp-note">{$t('analyticsPage.github.prsSampled', { values: { count: 100 } })}</span>
    {/if}
  {/if}
</ChartCard>

<style>
  .gp-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--s2) var(--s3);
    align-content: start;
  }
  .gp-stat {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }
  .gp-value {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .gp-label {
    font-size: 9.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .gp-hint {
    text-transform: none;
    letter-spacing: 0;
    font-weight: 400;
  }
  .gp-note {
    font-size: 9.5px;
    color: var(--text-muted);
    margin-top: auto;
  }

  @media (max-height: 760px) {
    .gp-grid {
      gap: var(--s1) var(--s3);
    }
    .gp-value {
      font-size: 13px;
    }
  }
</style>
