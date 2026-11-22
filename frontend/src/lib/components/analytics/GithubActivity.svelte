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

  type Payload = GithubStats & {
    source?: 'api' | 'webhook' | null;
    login?: string | null;
    truncated?: boolean;
    error?: 'rate_limited' | 'bad_credentials' | 'unavailable';
    stale?: boolean;
  };

  let { github, loading = false }: { github?: Payload; loading?: boolean } = $props();

  let W = $state(0);
  let H = $state(0);
  const M = { top: 14, right: 12, bottom: 26, left: 32 };

  const KEYS = ['pushes', 'pull_requests', 'issues', 'comments'] as const;
  const KEY_I18N: Record<(typeof KEYS)[number], string> = {
    pushes: 'analyticsPage.github.pushes',
    pull_requests: 'analyticsPage.github.prs',
    issues: 'analyticsPage.github.issues',
    comments: 'analyticsPage.github.comments',
  };
  const KEY_COLORS: Record<(typeof KEYS)[number], string> = {
    pushes: 'var(--xp)',
    pull_requests: 'var(--success)',
    issues: 'var(--link)',
    comments: 'var(--today)',
  };

  // Without GitHub data the chart shows a dimmed preview with a pointer to
  // Settings instead of disappearing, so the section is always discoverable.
  const GHOST: [number, number, number, number][] = [
    [3, 1, 0, 1], [5, 1, 1, 0], [4, 2, 0, 1], [7, 1, 1, 2], [6, 2, 1, 1], [9, 3, 1, 1],
    [5, 1, 0, 2], [8, 2, 2, 1], [10, 3, 1, 2], [7, 2, 1, 1], [12, 3, 2, 2], [9, 2, 1, 1],
  ];
  let real = $derived(github?.weekly ?? []);
  let showGhost = $derived(!github?.available || real.length === 0);
  let ghostWeeks = $derived.by<WeekRow[]>(() => {
    const monday = new Date();
    monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));
    return GHOST.map(([pushes, pull_requests, issues, comments], i) => {
      const d = new Date(monday);
      d.setDate(monday.getDate() - (GHOST.length - 1 - i) * 7);
      return { week_start: d.toISOString().slice(0, 10), pushes, pull_requests, issues, comments };
    });
  });
  let weeks = $derived(showGhost ? ghostWeeks : real);

  function openSettings() {
    window.dispatchEvent(new CustomEvent('joidy:open-settings'));
  }
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

<ChartCard title={$t('analyticsPage.slides.github')}>
  {#snippet icon()}<GitPullRequest size={13} />{/snippet}
  {#snippet actions()}
    {#if !showGhost && github?.source}
      <span
        class="gh-source mono"
        title={github.truncated ? $t('analyticsPage.github.truncated') : undefined}
      >
        {github.source === 'api'
          ? $t('analyticsPage.github.viaApi', { values: { login: github.login ?? '' } })
          : $t('analyticsPage.github.viaWebhook')}{#if github.truncated}
          · ⚠{/if}
      </span>
    {/if}
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

  <div class="gh-wrap" bind:this={wrapEl} bind:clientWidth={W} bind:clientHeight={H}>
      <svg
        width={W}
        height={H}
        role="img"
        aria-label={$t('analyticsPage.slides.github')}
        class:ghost={showGhost}
      >
        {#each yTicks as tv (tv)}
          <line x1={M.left} x2={W - M.right} y1={y(tv)} y2={y(tv)} class="grid-line" />
          {#if !showGhost}<text x={M.left - 8} y={y(tv) + 3} class="tick" text-anchor="end">{tv}</text>{/if}
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
              onmouseenter={(e) => !showGhost && onSeg(e, seg.data, key, p[1] - p[0])}
              onmousemove={(e) => !showGhost && onSeg(e, seg.data, key, p[1] - p[0])}
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

      {#if showGhost}
        <div class="gh-empty">
          <GitPullRequest size={20} />
          {#if loading}
            <span class="gh-empty-title">{$t('analyticsPage.github.loading')}</span>
          {:else}
            <span class="gh-empty-title"
              >{$t(
                github?.error
                  ? `analyticsPage.github.errorTitle_${github.error}`
                  : 'analyticsPage.github.emptyTitle'
              )}</span
            >
            <span class="gh-empty-body"
              >{$t(
                github?.error
                  ? `analyticsPage.github.errorBody_${github.error}`
                  : 'analyticsPage.github.empty'
              )}</span
            >
            <button type="button" class="gh-cta" onclick={openSettings}
              >{$t('analyticsPage.github.cta')}</button
            >
          {/if}
        </div>
      {/if}

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
            >{$t('analyticsPage.heatmap.events', {
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
    font-size: 10px;
    fill: var(--text-muted);
    font-family: var(--font-mono);
  }
  svg.ghost {
    opacity: 0.3;
  }
  .gh-empty {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -52%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    max-width: 320px;
    text-align: center;
    padding: var(--s4) var(--s5);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
  }
  .gh-empty-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
  }
  .gh-empty-body {
    font-size: 11px;
    line-height: 1.5;
  }
  .gh-cta {
    margin-top: var(--s2);
    padding: 5px 14px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: transparent;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s;
  }
  .gh-cta:hover {
    color: var(--xp);
    border-color: var(--xp);
  }
  .gh-seg {
    transition: opacity 0.12s ease;
  }
  .gh-seg:hover {
    opacity: 0.75;
  }
  .gh-source {
    font-size: 10px;
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
    color: var(--text-muted);
    white-space: nowrap;
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
    font-size: 10px;
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
</style>
