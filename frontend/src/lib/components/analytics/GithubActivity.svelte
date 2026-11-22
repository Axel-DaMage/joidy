<script lang="ts">
  import { scaleBand, scaleLinear, stack, max, type SeriesPoint } from 'd3';
  import GitPullRequest from 'lucide-svelte/icons/git-pull-request';
  import ChartCard from './ChartCard.svelte';
  import ChartTooltip from './ChartTooltip.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { parseLocalDate } from '$lib/utils/date';
  import { getLocale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';

  // Weekly GitHub activity, stacked bars (pushes / PRs / issues / comments)
  // over github.weekly (#1499). Only mounted when github.available is true.
  type GithubStats = AnalyticsOverview['github'];
  type WeekRow = GithubStats['weekly'][number];

  let { github }: { github?: GithubStats } = $props();

  let W = $state(0);
  let H = $state(0);
  const M = { top: 14, right: 12, bottom: 26, left: 32 };

  const KEYS = ['pushes', 'pull_requests', 'issues', 'comments'] as const;
  const KEY_I18N: Record<(typeof KEYS)[number], string> = {
    pushes: 'goalsAnalytics.github.pushes',
    pull_requests: 'goalsAnalytics.github.prs',
    issues: 'goalsAnalytics.github.issues',
    comments: 'goalsAnalytics.github.comments',
  };
  const KEY_COLORS: Record<(typeof KEYS)[number], string> = {
    pushes: 'var(--xp)',
    pull_requests: 'var(--success)',
    issues: 'var(--link)',
    comments: 'var(--today)',
  };

  let weeks = $derived(github?.weekly ?? []);
  let series = $derived(stack<WeekRow>().keys(KEYS)(weeks));

  let x = $derived(
    scaleBand<number>()
      .domain(weeks.map((_, i) => i))
      .range([M.left, Math.max(M.left + 1, W - M.right)])
      .paddingInner(0.35)
      .paddingOuter(0.15)
  );
  let maxTotal = $derived(
    Math.max(
      4,
      max(weeks, (w) => w.pushes + w.pull_requests + w.issues + w.comments) ?? 0
    )
  );
  let y = $derived(
    scaleLinear()
      .domain([0, maxTotal])
      .nice()
      .range([Math.max(M.top + 1, H - M.bottom), M.top])
  );
  let yTicks = $derived(y.ticks(4));

  let weekFmt = $derived(new Intl.DateTimeFormat(getLocale(), { day: 'numeric', month: 'short' }));
  function weekLabel(i: number): string {
    const w = weeks[i];
    return w ? weekFmt.format(parseLocalDate(w.week_start)) : '';
  }

  // ── Hover ──────────────────────────────────────────────────────────────────
  let wrapEl = $state<HTMLDivElement | null>(null);
  let tip = $state<{
    x: number;
    y: number;
    week: WeekRow;
    key: (typeof KEYS)[number];
    value: number;
  } | null>(null);

  function onSeg(
    e: MouseEvent,
    week: WeekRow,
    key: (typeof KEYS)[number],
    value: number
  ) {
    if (!wrapEl) return;
    const r = wrapEl.getBoundingClientRect();
    tip = { x: e.clientX - r.left, y: e.clientY - r.top, week, key, value };
  }
</script>

<ChartCard title={$t('goalsAnalytics.slides.github')}>
  {#snippet icon()}<GitPullRequest size={13} />{/snippet}
  {#snippet actions()}
    <div class="gh-legend">
      {#each KEYS as k (k)}
        <span class="gh-leg"
          ><span class="gh-dot" style="background: {KEY_COLORS[k]}"></span>{$t(
            KEY_I18N[k]
          )}</span
        >
      {/each}
    </div>
  {/snippet}

  {#if weeks.length === 0}
    <div class="chart-empty">
      <GitPullRequest size={22} style="opacity:0.25" />
      <span>{$t('goalsAnalytics.github.empty')}</span>
    </div>
  {:else}
    <div class="gh-wrap" bind:this={wrapEl} bind:clientWidth={W} bind:clientHeight={H}>
      <svg
        width={W}
        height={H}
        role="img"
        aria-label={$t('goalsAnalytics.slides.github')}
      >
        {#each yTicks as tv (tv)}
          <line x1={M.left} x2={W - M.right} y1={y(tv)} y2={y(tv)} class="grid-line" />
          <text x={M.left - 8} y={y(tv) + 3} class="tick" text-anchor="end">{tv}</text>
        {/each}
        <line x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} class="axis" />

        {#each series as s (s.key)}
          {@const key = s.key as (typeof KEYS)[number]}
          {#each s as seg (seg.data.week_start)}
            {@const i = weeks.indexOf(seg.data)}
            {@const p = seg as SeriesPoint<WeekRow>}
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <rect
              x={x(i)}
              y={y(p[1])}
              width={x.bandwidth()}
              height={Math.max(0, y(p[0]) - y(p[1]))}
              rx="2"
              fill={KEY_COLORS[key]}
              class="gh-seg"
              onmouseenter={(e) => onSeg(e, seg.data, key, p[1] - p[0])}
              onmousemove={(e) => onSeg(e, seg.data, key, p[1] - p[0])}
              onmouseleave={() => (tip = null)}
            />
          {/each}
        {/each}

        {#each weeks as w, i (w.week_start)}
          {#if i % Math.ceil(weeks.length / 10) === 0 || i === weeks.length - 1}
            <text
              x={(x(i) ?? 0) + x.bandwidth() / 2}
              y={H - M.bottom + 14}
              class="tick"
              text-anchor="middle">{weekLabel(i)}</text
            >
          {/if}
        {/each}
      </svg>

      <ChartTooltip
        x={tip?.x ?? 0}
        y={tip?.y ?? 0}
        visible={!!tip}
        placeBelow={(tip?.y ?? 0) < 70}
      >
        {#if tip}
          <span class="tt-title">{weekFmt.format(parseLocalDate(tip.week.week_start))}</span>
          <span class="tt-row"
            ><span class="tt-dot" style="background: {KEY_COLORS[tip.key]}"></span>{$t(
              KEY_I18N[tip.key]
            )}<span class="tt-val">{tip.value}</span></span
          >
          <span class="tt-row"
            >{$t('goalsAnalytics.heatmap.events', {
              values: {
                count:
                  tip.week.pushes +
                  tip.week.pull_requests +
                  tip.week.issues +
                  tip.week.comments,
              },
            })}</span
          >
        {/if}
      </ChartTooltip>
    </div>
  {/if}
</ChartCard>

<style>
  .gh-wrap {
    position: relative;
    flex: 1;
    min-height: 0;
  }
  svg {
    position: absolute;
    inset: 0;
    display: block;
  }
  .grid-line {
    stroke: var(--border);
    stroke-width: 0.5;
    opacity: 0.5;
  }
  .axis {
    stroke: var(--border);
    stroke-width: 1;
  }
  .tick {
    font-size: 9px;
    fill: var(--text-muted);
    font-family: var(--font-mono);
  }
  .gh-seg {
    transition: opacity 0.12s ease;
  }
  .gh-seg:hover {
    opacity: 0.75;
  }
  .gh-legend {
    display: flex;
    gap: var(--s3);
    flex-wrap: wrap;
  }
  .gh-leg {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 9px;
    color: var(--text-muted);
    text-transform: none;
    letter-spacing: 0;
    font-weight: 400;
  }
  .gh-dot {
    width: 8px;
    height: 8px;
    border-radius: 2px;
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
</style>
