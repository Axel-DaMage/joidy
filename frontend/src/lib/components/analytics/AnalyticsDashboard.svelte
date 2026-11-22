<script lang="ts">
  import { onMount } from 'svelte';
  import { fly } from 'svelte/transition';
  import ChevronLeft from 'lucide-svelte/icons/chevron-left';
  import ChevronRight from 'lucide-svelte/icons/chevron-right';
  import Zap from 'lucide-svelte/icons/zap';
  import Flame from 'lucide-svelte/icons/flame';
  import CalendarCheck from 'lucide-svelte/icons/calendar-check';
  import TrendingUp from 'lucide-svelte/icons/trending-up';
  import TrendingDown from 'lucide-svelte/icons/trending-down';
  import Trophy from 'lucide-svelte/icons/trophy';
  import Clock from 'lucide-svelte/icons/clock';
  import Smile from 'lucide-svelte/icons/smile';
  import Target from 'lucide-svelte/icons/target';
  import GitPullRequest from 'lucide-svelte/icons/git-pull-request';
  import Sigma from 'lucide-svelte/icons/sigma';
  import TriangleAlert from 'lucide-svelte/icons/triangle-alert';
  import { api, type AnalyticsOverview } from '$lib/api';
  import { loadUserSettings, patchUserSettings } from '$lib/utils/userSettings';
  import { parseLocalDate } from '$lib/utils/date';
  import { locale, getLocale } from '$lib/stores/locale';
  import { use24HourClock } from '$lib/stores/settings';
  import { insightsFor, type InsightCtx } from '$lib/utils/insights';
  import { logger } from '$lib/utils/logger';
  import { t } from 'svelte-i18n';
  import ConsistencyHeatmap from './ConsistencyHeatmap.svelte';
  import ProductivityTrend from './ProductivityTrend.svelte';
  import ActivityClock from './ActivityClock.svelte';
  import WeekdayBars from './WeekdayBars.svelte';
  import ActivityBands from './ActivityBands.svelte';
  import StreakPanel from './StreakPanel.svelte';
  import RecentDays from './RecentDays.svelte';
  import InsightPanel from './InsightPanel.svelte';
  import MoodProductivity from './MoodProductivity.svelte';
  import XpSources from './XpSources.svelte';
  import GoalsOverview from './GoalsOverview.svelte';
  import GithubActivity from './GithubActivity.svelte';
  import SeasonMatrix from './SeasonMatrix.svelte';
  import PeriodCompare from './PeriodCompare.svelte';
  import WeeklyRhythm from './WeeklyRhythm.svelte';
  import GoalStates from './GoalStates.svelte';
  import CountUp from './CountUp.svelte';
  import Sparkline from './Sparkline.svelte';

  // Holistic analytics dashboard (#1499) — vertical KPI rail + a bento
  // carousel: every slide is a CSS-grid of tiles (hero + auxiliary) next to a
  // deterministic-insights panel, sized to the viewport so nothing scrolls.
  const SLIDES = [
    { id: 'consistency', label: 'goalsAnalytics.slides.consistency', icon: CalendarCheck },
    { id: 'trend', label: 'goalsAnalytics.slides.trend', icon: TrendingUp },
    { id: 'seasonality', label: 'goalsAnalytics.slides.seasonality', icon: Clock },
    { id: 'mood', label: 'goalsAnalytics.slides.mood', icon: Smile },
    { id: 'goals', label: 'goalsAnalytics.slides.goals', icon: Target },
    { id: 'github', label: 'goalsAnalytics.slides.github', icon: GitPullRequest },
  ] as const;

  type SlideId = (typeof SLIDES)[number]['id'];

  let data = $state<AnalyticsOverview | null>(null);
  let loading = $state(true);
  let loadError = $state(false);
  // Global analysis window (days) — drives every slide, not just the heatmap.
  let rangeDays = $state(180);
  let slideIdx = $state(0);
  let slideDir = $state(1);
  let prefsReady = $state(false);

  // The GitHub slide only exists when the backend reports data for it.
  let slides = $derived(
    SLIDES.filter((s) => s.id !== 'github' || (data?.github.available ?? false))
  );

  // Keep the restored index inside the (possibly shorter) visible list.
  $effect(() => {
    if (slideIdx >= slides.length) slideIdx = Math.max(0, slides.length - 1);
  });

  // Persist the active slide — same pattern as GithubWidget's activityTab.
  $effect(() => {
    if (prefsReady) patchUserSettings({ analyticsUi: { slide: slideIdx } });
  });

  function prevSlide() {
    slideDir = -1;
    slideIdx = (slideIdx - 1 + slides.length) % slides.length;
  }
  function nextSlide() {
    slideDir = 1;
    slideIdx = (slideIdx + 1) % slides.length;
  }
  function goToSlide(i: number) {
    slideDir = i > slideIdx ? 1 : -1;
    slideIdx = i;
  }
  function onKeydown(e: KeyboardEvent) {
    // Arrow keys navigate slides unless the user is typing in a field.
    const el = e.target as HTMLElement;
    if (el.closest('input, textarea, [contenteditable="true"]')) return;
    if (e.key === 'ArrowLeft') prevSlide();
    else if (e.key === 'ArrowRight') nextSlide();
  }

  async function load(days: number) {
    if (!data) loading = true;
    loadError = false;
    try {
      data = await api.analytics.overview(days);
    } catch (e) {
      logger.error('[analytics] overview failed:', e);
      if (!data) loadError = true;
    } finally {
      loading = false;
    }
  }

  const RANGES = [90, 180, 365] as const;

  function setRangeDays(days: number) {
    if (days === rangeDays) return;
    rangeDays = days;
    patchUserSettings({ analyticsUi: { rangeDays: days } });
    void load(days);
  }

  // Locale/format context shared by the deterministic insight rules —
  // every derived that reads it re-runs on locale/clock-format changes.
  let insightCtx = $derived<InsightCtx>({
    t: (key, opts) => $t(key, opts),
    fmtDate: (iso) =>
      new Intl.DateTimeFormat($locale, { day: 'numeric', month: 'short' }).format(
        parseLocalDate(iso)
      ),
    fmtWeekday: (i) =>
      new Intl.DateTimeFormat($locale, { weekday: 'long' }).format(new Date(2024, 0, 1 + i)),
    fmtHour: (h) =>
      $use24HourClock
        ? `${String(h).padStart(2, '0')}:00`
        : h === 0
          ? '12am'
          : h < 12
            ? `${h}am`
            : h === 12
              ? '12pm'
              : `${h - 12}pm`,
  });

  let slideInsights = $derived(
    data ? insightsFor(slides[slideIdx]?.id ?? 'consistency', data, insightCtx) : []
  );

  let bestDay = $derived.by(() => {
    const best = data?.summary.best_day;
    if (!best) return null;
    const d = new Intl.DateTimeFormat(getLocale(), { day: 'numeric', month: 'short' });
    return { xp: best.xp, date: d.format(parseLocalDate(best.date)) };
  });

  // Window XP vs the equally long window before it (null = nothing to compare).
  let xpDelta = $derived.by(() => {
    const s = data?.summary;
    if (!s || s.prev_total_xp <= 0) return null;
    return Math.round(((s.window_xp - s.prev_total_xp) / s.prev_total_xp) * 100);
  });
  let xpSpark = $derived((data?.daily_activity ?? []).map((d) => Math.max(0, d.xp)));
  let activeShare = $derived(
    data && data.days > 0 ? Math.round((data.summary.active_days / data.days) * 100) : 0
  );
  let perActiveDay = $derived(
    data && data.summary.active_days > 0
      ? Math.round(data.summary.window_xp / data.summary.active_days)
      : 0
  );

  onMount(() => {
    try {
      const saved = loadUserSettings().analyticsUi;
      if (typeof saved?.slide === 'number' && saved.slide >= 0) {
        slideIdx = saved.slide;
      }
      if (saved?.rangeDays === 90 || saved?.rangeDays === 180 || saved?.rangeDays === 365) {
        rangeDays = saved.rangeDays;
      }
    } catch {
      // ignore storage errors
    }
    prefsReady = true;
    void load(rangeDays);
  });
</script>

<svelte:window onkeydown={onKeydown} />

{#snippet slideBody(id: SlideId | undefined)}
  {#if data}
    {#if id === 'consistency'}
      <div class="ad-grid g-consistency">
        <div class="a-heat"><ConsistencyHeatmap activity={data.daily_activity} days={rangeDays} /></div>
        <div class="a-streak"><StreakPanel streaks={data.streaks} /></div>
        <div class="a-weekly"><WeeklyRhythm activity={data.daily_activity} /></div>
        <div class="a-wday"><WeekdayBars activity={data.daily_activity} /></div>
      </div>
    {:else if id === 'trend'}
      <div class="ad-grid g-trend">
        <div class="a-main"><ProductivityTrend activity={data.daily_activity} /></div>
        <div class="a-src"><XpSources byType={data.xp_by_type} /></div>
        <div class="a-cmp"><PeriodCompare summary={data.summary} /></div>
      </div>
    {:else if id === 'seasonality'}
      <div class="ad-grid g-season">
        <div class="a-clock"><ActivityClock seasonality={data.seasonality} /></div>
        <div class="a-matrix"><SeasonMatrix seasonality={data.seasonality} /></div>
        <div class="a-bands"><ActivityBands seasonality={data.seasonality} /></div>
        <div class="a-wday"><WeekdayBars activity={data.daily_activity} /></div>
      </div>
    {:else if id === 'mood'}
      <div class="ad-grid g-wide">
        <div class="a-main"><MoodProductivity mood={data.mood_activity} /></div>
        <div class="a-recent"><RecentDays activity={data.daily_activity} /></div>
        <div class="a-wday"><WeekdayBars activity={data.daily_activity} /></div>
      </div>
    {:else if id === 'goals'}
      <div class="ad-grid g-goals">
        <div class="a-main"><GoalsOverview goals={data.goals} /></div>
        <div class="a-states"><GoalStates goals={data.goals} /></div>
        <div class="a-streak"><StreakPanel streaks={data.streaks} /></div>
      </div>
    {:else if id === 'github'}
      <div class="ad-grid g-wide">
        <div class="a-main"><GithubActivity github={data.github} /></div>
        <div class="a-recent"><RecentDays activity={data.daily_activity} /></div>
        <div class="a-wday"><WeekdayBars activity={data.daily_activity} /></div>
      </div>
    {/if}
  {/if}
{/snippet}

<div class="ad-root">
  {#if loading}
    <div class="ad-rail ad-rail-skeleton">
      {#each [0, 1, 2, 3, 4, 5] as i (i)}
        <div class="ad-kpi">
          <div class="sk sk-icon"></div>
          <div class="sk sk-line"></div>
        </div>
      {/each}
    </div>
    <div class="ad-slide-skeleton">
      <div class="sk sk-tile sk-big"></div>
      <div class="sk sk-tile"></div>
      <div class="sk sk-tile"></div>
      <span class="ad-loading-label">{$t('goalsAnalytics.loading')}</span>
    </div>
  {:else if loadError}
    <div class="ad-error">
      <TriangleAlert size={22} style="opacity:0.5" />
      <span>{$t('goalsAnalytics.loadError')}</span>
      <button type="button" class="ad-retry" onclick={() => void load(rangeDays)}
        >{$t('common.retry')}</button
      >
    </div>
  {:else if data}
    <!-- Vertical KPI rail -->
    <aside class="ad-rail">
      <span class="ad-rail-title">{$t('goalsAnalytics.railTitle')}</span>

      <div class="ad-hero">
        <div class="ad-hero-head">
          <span class="ad-kpi-label">{$t('goalsAnalytics.kpi.windowXp')}</span>
          {#if xpDelta !== null}
            <span class="ad-delta" class:up={xpDelta >= 5} class:down={xpDelta <= -5}>
              {#if xpDelta <= -5}<TrendingDown size={11} />{:else}<TrendingUp size={11} />{/if}
              {xpDelta > 0 ? '+' : ''}{xpDelta}%
            </span>
          {/if}
        </div>
        <span class="ad-hero-val"><CountUp value={data.summary.window_xp} /></span>
        <div class="ad-spark"><Sparkline values={xpSpark} color="var(--xp)" /></div>
      </div>

      <div class="ad-kpis">
        <div class="ad-kpi">
          <span class="ad-kpi-icon"><Flame size={14} /></span>
          <div class="ad-kpi-txt">
            <span class="ad-kpi-label">{$t('goalsAnalytics.statStreak')}</span>
            <span class="ad-kpi-val"><CountUp value={data.streaks.current_streak} />d</span>
            <span class="ad-kpi-sub"
              >{$t('goalsAnalytics.kpi.record', { values: { days: data.streaks.longest_streak } })}</span
            >
          </div>
        </div>
        <div class="ad-kpi">
          <span class="ad-kpi-icon"><CalendarCheck size={14} /></span>
          <div class="ad-kpi-txt">
            <span class="ad-kpi-label">{$t('goalsAnalytics.statActiveDays')}</span>
            <span class="ad-kpi-val"
              ><CountUp value={data.summary.active_days} /><span class="ad-kpi-of">/{data.days}</span></span
            >
            <div class="ad-meter"><div class="ad-meter-fill" style:width="{activeShare}%"></div></div>
          </div>
        </div>
        <div class="ad-kpi">
          <span class="ad-kpi-icon"><Zap size={14} /></span>
          <div class="ad-kpi-txt">
            <span class="ad-kpi-label">{$t('goalsAnalytics.statAvgXp')}</span>
            <span class="ad-kpi-val"><CountUp value={data.summary.avg_daily_xp} /></span>
            <span class="ad-kpi-sub"
              >{$t('goalsAnalytics.kpi.perActiveDay', { values: { xp: perActiveDay.toLocaleString() } })}</span
            >
          </div>
        </div>
        <div class="ad-kpi">
          <span class="ad-kpi-icon"><Trophy size={14} /></span>
          <div class="ad-kpi-txt">
            <span class="ad-kpi-label">{$t('goalsAnalytics.statBestDay')}</span>
            <span class="ad-kpi-val">{bestDay ? bestDay.xp.toLocaleString() : '—'}</span>
            <span class="ad-kpi-sub">{bestDay ? bestDay.date : ''}</span>
          </div>
        </div>
        <div class="ad-kpi">
          <span class="ad-kpi-icon"><Sigma size={14} /></span>
          <div class="ad-kpi-txt">
            <span class="ad-kpi-label">{$t('goalsAnalytics.statTotalXp')}</span>
            <span class="ad-kpi-val"><CountUp value={data.summary.total_xp} /></span>
            <span class="ad-kpi-sub">{$t('goalsAnalytics.kpi.accumulated')}</span>
          </div>
        </div>
      </div>

      <!-- Global analysis window — re-windows every slide (#1499) -->
      <div class="ad-range-wrap">
        <span class="ad-kpi-label">{$t('goalsAnalytics.rangeLabel')}</span>
        <div class="ad-range" role="group" aria-label={$t('goalsAnalytics.rangeLabel')}>
          {#each RANGES as r (r)}
            <button
              type="button"
              class="ad-range-btn"
              class:active={rangeDays === r}
              title={$t(`goalsAnalytics.range${r}`)}
              onclick={() => setRangeDays(r)}>{$t(`goalsAnalytics.range${r}Short`)}</button
            >
          {/each}
        </div>
      </div>
    </aside>

    <!-- Carousel -->
    <div class="ad-carousel">
      <div class="ad-viewport">
        <button
          type="button"
          class="ad-arrow"
          onclick={prevSlide}
          title={$t('common.previous')}
          aria-label={$t('common.previous')}><ChevronLeft size={16} /></button
        >

        <div class="ad-stage">
          {#key slideIdx}
            <div class="ad-slide" in:fly={{ x: slideDir * 40, duration: 240, opacity: 0 }}>
              <div class="ad-slide-charts">{@render slideBody(slides[slideIdx]?.id)}</div>
              <InsightPanel items={slideInsights} methodKey={slides[slideIdx]?.id} />
            </div>
          {/key}
        </div>

        <button
          type="button"
          class="ad-arrow"
          onclick={nextSlide}
          title={$t('common.next')}
          aria-label={$t('common.next')}><ChevronRight size={16} /></button
        >
      </div>

      <div class="ad-tabs" role="tablist">
        {#each slides as s, i (s.id)}
          {@const Icon = s.icon}
          <button
            type="button"
            role="tab"
            class="ad-tab"
            class:active={i === slideIdx}
            aria-selected={i === slideIdx}
            onclick={() => goToSlide(i)}
          >
            <Icon size={13} />
            <span>{$t(`goalsAnalytics.tabs.${s.id}`)}</span>
          </button>
        {/each}
      </div>
    </div>
  {:else}
    <div class="ad-error">
      <span>{$t('goalsAnalytics.empty')}</span>
    </div>
  {/if}
</div>

<style>
  .ad-root {
    position: relative;
    display: flex;
    gap: var(--s3);
    width: 100%;
    flex: 1;
    min-height: 0;
  }

  /* ── Vertical KPI rail ── */
  .ad-rail {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    width: 212px;
    flex-shrink: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3) var(--s4);
    backdrop-filter: blur(10px);
    overflow: hidden;
    min-height: 0;
  }
  .ad-rail-title {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .ad-hero {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex-shrink: 0;
  }
  .ad-hero-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s2);
  }
  .ad-hero-val {
    font-size: 30px;
    font-weight: 700;
    line-height: 1.05;
    font-family: var(--font-mono);
    color: var(--text-primary);
  }
  .ad-spark {
    height: 44px;
    margin-top: 2px;
  }
  .ad-delta {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: 10px;
    font-weight: 700;
    font-family: var(--font-mono);
    color: var(--text-muted);
  }
  .ad-delta.up {
    color: var(--success);
  }
  .ad-delta.down {
    color: var(--error);
  }
  .ad-kpis {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .ad-kpi {
    flex: 1 1 0;
    min-height: 0;
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
    border-top: 1px solid var(--border);
    animation: ad-fade 0.4s ease both;
  }
  .ad-kpi-icon {
    display: flex;
    color: var(--text-muted);
    flex-shrink: 0;
  }
  .ad-kpi-txt {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    flex: 1;
  }
  .ad-kpi-label {
    font-size: 9px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-family: var(--font-mono);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .ad-kpi-val {
    font-size: 18px;
    font-weight: 700;
    font-family: var(--font-mono);
    line-height: 1.15;
    color: var(--text-primary);
    white-space: nowrap;
  }
  .ad-kpi-of {
    font-size: 11px;
    font-weight: 400;
    color: var(--text-muted);
  }
  .ad-kpi-sub {
    font-size: 10px;
    color: var(--text-muted);
    min-height: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .ad-meter {
    height: 4px;
    border-radius: 2px;
    background: color-mix(in srgb, var(--text-primary) 8%, transparent);
    overflow: hidden;
    margin-top: 3px;
  }
  .ad-meter-fill {
    height: 100%;
    border-radius: 2px;
    background: var(--xp);
    transition: width 0.6s ease;
  }
  .ad-range-wrap {
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex-shrink: 0;
    border-top: 1px solid var(--border);
    padding-top: var(--s3);
  }
  .ad-range {
    display: flex;
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
  }
  .ad-range-btn {
    flex: 1;
    padding: 5px 0;
    border: none;
    border-left: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    font-size: 10px;
    font-weight: 600;
    font-family: var(--font-mono);
    cursor: pointer;
    transition: all 0.15s;
  }
  .ad-range-btn:first-child {
    border-left: none;
  }
  .ad-range-btn:hover {
    color: var(--text-secondary);
  }
  .ad-range-btn.active {
    color: var(--xp);
    background: color-mix(in srgb, var(--xp) 12%, transparent);
  }

  /* ── Carousel ── */
  .ad-carousel {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    flex: 1;
    min-width: 0;
    min-height: 0;
  }
  .ad-viewport {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: 30px minmax(0, 1fr) 30px;
    gap: var(--s2);
  }
  .ad-stage {
    position: relative;
    min-width: 0;
    min-height: 0;
  }
  .ad-slide {
    position: absolute;
    inset: 0;
    display: grid;
    grid-template-columns: minmax(0, 1fr) 280px;
    gap: var(--s3);
  }
  .ad-slide-charts {
    min-width: 0;
    min-height: 0;
    display: flex;
  }
  .ad-arrow {
    align-self: center;
    display: grid;
    place-items: center;
    width: 30px;
    height: 56px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }
  .ad-arrow:hover {
    color: var(--text-primary);
    border-color: var(--primary);
    background: var(--surface-hover);
  }
  .ad-arrow:focus-visible {
    outline: 1px solid var(--xp);
    outline-offset: 2px;
  }

  /* ── Tile grids (one per slide) ── */
  .ad-grid {
    flex: 1;
    min-width: 0;
    min-height: 0;
    display: grid;
    gap: var(--s3);
  }
  .ad-grid > div {
    min-width: 0;
    min-height: 0;
  }
  .g-consistency {
    grid-template-columns: 1.1fr 1.1fr 0.95fr;
    grid-template-rows: auto minmax(0, 1fr);
    grid-template-areas:
      'heat heat streak'
      'weekly weekly wday';
  }
  .g-trend {
    grid-template-columns: 1.4fr 1fr;
    grid-template-rows: minmax(0, 1.45fr) minmax(0, 1fr);
    grid-template-areas:
      'main main'
      'src cmp';
  }
  .g-season {
    grid-template-columns: 1fr 1.35fr;
    grid-template-rows: minmax(0, 1.3fr) minmax(0, 1fr);
    grid-template-areas:
      'clock matrix'
      'bands wday';
  }
  .g-wide {
    grid-template-columns: 1.4fr 1fr;
    grid-template-rows: minmax(0, 1.5fr) minmax(0, 1fr);
    grid-template-areas:
      'main main'
      'recent wday';
  }
  .g-goals {
    grid-template-columns: 1fr 1fr;
    grid-template-rows: minmax(0, 1.15fr) minmax(0, 1fr);
    grid-template-areas:
      'main main'
      'states streak';
  }
  .a-heat {
    grid-area: heat;
  }
  .a-streak {
    grid-area: streak;
  }
  .a-weekly {
    grid-area: weekly;
  }
  .a-wday {
    grid-area: wday;
  }
  .a-main {
    grid-area: main;
  }
  .a-src {
    grid-area: src;
  }
  .a-cmp {
    grid-area: cmp;
  }
  .a-clock {
    grid-area: clock;
  }
  .a-matrix {
    grid-area: matrix;
  }
  .a-bands {
    grid-area: bands;
  }
  .a-recent {
    grid-area: recent;
  }
  .a-states {
    grid-area: states;
  }
  .ad-grid > :nth-child(2) :global(.ac-card) {
    animation-delay: 60ms;
  }
  .ad-grid > :nth-child(3) :global(.ac-card) {
    animation-delay: 120ms;
  }
  .ad-grid > :nth-child(4) :global(.ac-card) {
    animation-delay: 180ms;
  }

  /* ── Tabs ── */
  .ad-tabs {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: var(--s5);
    flex-shrink: 0;
    padding-top: 2px;
  }
  .ad-tab {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 3px 0;
    cursor: pointer;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    transition: all var(--t-fast, 0.15s);
  }
  .ad-tab:hover {
    color: var(--text-secondary);
  }
  .ad-tab.active {
    color: var(--text-primary);
    border-bottom-color: var(--accent);
  }

  /* ── Skeleton / error ── */
  .sk {
    background: linear-gradient(
      100deg,
      color-mix(in srgb, var(--text-primary) 5%, transparent) 40%,
      color-mix(in srgb, var(--text-primary) 10%, transparent) 50%,
      color-mix(in srgb, var(--text-primary) 5%, transparent) 60%
    );
    background-size: 200% 100%;
    animation: ad-shimmer 1.4s infinite linear;
    border-radius: var(--r);
  }
  @keyframes ad-shimmer {
    from {
      background-position: 200% 0;
    }
    to {
      background-position: -200% 0;
    }
  }
  @keyframes ad-fade {
    from {
      opacity: 0;
      transform: translateY(4px);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
  .ad-rail-skeleton .ad-kpi {
    border-top: none;
  }
  .sk-icon {
    width: 26px;
    height: 26px;
    flex-shrink: 0;
  }
  .sk-line {
    width: 80px;
    height: 14px;
  }
  .ad-slide-skeleton {
    position: relative;
    flex: 1;
    min-width: 0;
    display: grid;
    grid-template-columns: 1.4fr 1fr;
    grid-template-rows: 1.5fr 1fr;
    gap: var(--s3);
  }
  .sk-big {
    grid-column: 1 / -1;
  }
  .ad-loading-label {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    pointer-events: none;
  }
  .ad-error {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--s3);
    padding: var(--s6) var(--s4);
    color: var(--text-muted);
    font-size: 12px;
    text-align: center;
  }
  .ad-retry {
    padding: 6px 14px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
  }
  .ad-retry:hover {
    color: var(--xp);
    border-color: var(--xp);
  }

  /* Short viewports: drop secondary rail lines instead of scrolling. */
  @media (max-height: 800px) {
    .ad-kpi-sub,
    .ad-meter {
      display: none;
    }
    .ad-spark {
      height: 34px;
    }
  }
  @media (max-width: 1280px) {
    .ad-slide {
      grid-template-columns: minmax(0, 1fr) 240px;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .ad-kpi {
      animation: none;
    }
  }

  @media (max-width: 900px) {
    .ad-root {
      flex-direction: column;
    }
    .ad-rail {
      width: 100%;
      overflow-x: auto;
    }
    .ad-viewport {
      grid-template-columns: minmax(0, 1fr);
    }
    .ad-arrow {
      display: none;
    }
    .ad-stage {
      min-height: 0;
    }
    .ad-slide {
      position: relative;
      grid-template-columns: 1fr;
    }
    .ad-tabs {
      flex-wrap: wrap;
      gap: var(--s3);
    }
  }
</style>
