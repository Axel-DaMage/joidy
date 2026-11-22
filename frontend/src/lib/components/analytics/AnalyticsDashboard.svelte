<script lang="ts">
  import { onMount } from 'svelte';
  import { fly } from 'svelte/transition';
  import ChevronLeft from 'lucide-svelte/icons/chevron-left';
  import ChevronRight from 'lucide-svelte/icons/chevron-right';
  import Zap from 'lucide-svelte/icons/zap';
  import Flame from 'lucide-svelte/icons/flame';
  import Award from 'lucide-svelte/icons/award';
  import CalendarCheck from 'lucide-svelte/icons/calendar-check';
  import TrendingUp from 'lucide-svelte/icons/trending-up';
  import Trophy from 'lucide-svelte/icons/trophy';
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

  // Holistic analytics dashboard (#1499) — vertical KPI rail + a bento
  // carousel: every slide composes a hero chart with auxiliary tiles and
  // a deterministic-insights panel so the viewport is always filled.
  const SLIDES = [
    { id: 'consistency', label: 'goalsAnalytics.slides.consistency' },
    { id: 'trend', label: 'goalsAnalytics.slides.trend' },
    { id: 'seasonality', label: 'goalsAnalytics.slides.seasonality' },
    { id: 'mood', label: 'goalsAnalytics.slides.mood' },
    { id: 'goals', label: 'goalsAnalytics.slides.goals' },
    { id: 'github', label: 'goalsAnalytics.slides.github' },
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

  let bestDayLabel = $derived.by(() => {
    const best = data?.summary.best_day;
    if (!best) return '—';
    const d = new Intl.DateTimeFormat(getLocale(), { day: 'numeric', month: 'short' });
    return `${d.format(parseLocalDate(best.date))} · ${best.xp} XP`;
  });

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

{#snippet heroChart(id: SlideId | undefined)}
  {#if data}
    {#if id === 'consistency'}
      <ConsistencyHeatmap activity={data.daily_activity} days={rangeDays} />
    {:else if id === 'trend'}
      <ProductivityTrend activity={data.daily_activity} />
    {:else if id === 'seasonality'}
      <ActivityClock seasonality={data.seasonality} />
    {:else if id === 'mood'}
      <MoodProductivity mood={data.mood_activity} />
    {:else if id === 'goals'}
      <GoalsOverview goals={data.goals} streaks={data.streaks} />
    {:else if id === 'github'}
      <GithubActivity github={data.github} />
    {/if}
  {/if}
{/snippet}

{#snippet auxTiles(id: SlideId | undefined)}
  {#if data}
    {#if id === 'consistency'}
      <div class="ad-aux">
        <StreakPanel streaks={data.streaks} />
        <WeekdayBars activity={data.daily_activity} />
      </div>
    {:else if id === 'trend'}
      <div class="ad-aux">
        <XpSources byType={data.xp_by_type} />
      </div>
    {:else if id === 'seasonality'}
      <div class="ad-aux">
        <ActivityBands seasonality={data.seasonality} />
        <WeekdayBars activity={data.daily_activity} />
      </div>
    {:else if id === 'mood' || id === 'goals'}
      <div class="ad-aux">
        <RecentDays activity={data.daily_activity} />
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
    <div class="ad-slide-skeleton sk"></div>
    <span class="ad-loading-label">{$t('goalsAnalytics.loading')}</span>
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

      <div class="ad-kpi">
        <span class="ad-kpi-icon" style="color: var(--xp)"><Zap size={15} /></span>
        <div class="ad-kpi-txt">
          <span class="ad-kpi-label">{$t('goalsAnalytics.statTotalXp')}</span>
          <span class="ad-kpi-val">{data.summary.total_xp.toLocaleString()}</span>
        </div>
      </div>
      <div class="ad-kpi">
        <span class="ad-kpi-icon" style="color: var(--today)"><Flame size={15} /></span>
        <div class="ad-kpi-txt">
          <span class="ad-kpi-label">{$t('goalsAnalytics.statStreak')}</span>
          <span class="ad-kpi-val">{data.streaks.current_streak}d</span>
        </div>
      </div>
      <div class="ad-kpi">
        <span class="ad-kpi-icon" style="color: var(--success)"><CalendarCheck size={15} /></span>
        <div class="ad-kpi-txt">
          <span class="ad-kpi-label">{$t('goalsAnalytics.statActiveDays')}</span>
          <span class="ad-kpi-val">{data.summary.active_days}</span>
        </div>
      </div>
      <div class="ad-kpi">
        <span class="ad-kpi-icon" style="color: var(--link)"><TrendingUp size={15} /></span>
        <div class="ad-kpi-txt">
          <span class="ad-kpi-label">{$t('goalsAnalytics.statAvgXp')}</span>
          <span class="ad-kpi-val">{Math.round(data.summary.avg_daily_xp)}</span>
        </div>
      </div>
      <div class="ad-kpi">
        <span class="ad-kpi-icon" style="color: var(--today)"><Award size={15} /></span>
        <div class="ad-kpi-txt">
          <span class="ad-kpi-label">{$t('goalsAnalytics.statBestStreak')}</span>
          <span class="ad-kpi-val">{data.streaks.longest_streak}d</span>
        </div>
      </div>
      <div class="ad-kpi">
        <span class="ad-kpi-icon" style="color: var(--xp)"><Trophy size={15} /></span>
        <div class="ad-kpi-txt">
          <span class="ad-kpi-label">{$t('goalsAnalytics.statBestDay')}</span>
          <span class="ad-kpi-val ad-kpi-best">{bestDayLabel}</span>
        </div>
      </div>

      <div class="ad-rail-sep"></div>

      <!-- Global analysis window — re-windows every slide (#1499) -->
      <span class="ad-range-label">{$t('goalsAnalytics.rangeLabel')}</span>
      <div class="ad-range" role="group" aria-label={$t('goalsAnalytics.rangeLabel')}>
        {#each RANGES as r (r)}
          <button
            type="button"
            class="ad-range-btn"
            class:active={rangeDays === r}
            onclick={() => setRangeDays(r)}
            >{$t(`goalsAnalytics.range${r}`)}</button
          >
        {/each}
      </div>
    </aside>

    <!-- Carousel -->
    <div class="ad-carousel">
      <div class="ad-viewport">
        {#key slideIdx}
          <div class="ad-slide" in:fly={{ x: slideDir * 48, duration: 240, opacity: 0 }}>
            <div class="ad-slide-charts">
              <div class="ad-hero">{@render heroChart(slides[slideIdx]?.id)}</div>
              {@render auxTiles(slides[slideIdx]?.id)}
            </div>
            <InsightPanel items={slideInsights} />
          </div>
        {/key}

        <!-- Floating edge arrows -->
        <button
          type="button"
          class="ad-arrow-float prev"
          onclick={prevSlide}
          title={$t('common.previous')}
          aria-label={$t('common.previous')}><ChevronLeft size={18} /></button
        >
        <button
          type="button"
          class="ad-arrow-float next"
          onclick={nextSlide}
          title={$t('common.next')}
          aria-label={$t('common.next')}><ChevronRight size={18} /></button
        >
      </div>

      <div class="ad-foot">
        <div class="ad-dots">
          {#each slides as s, i (s.id)}
            <button
              type="button"
              class="ad-dot"
              class:active={i === slideIdx}
              onclick={() => goToSlide(i)}
              aria-label={$t(s.label)}
            ></button>
          {/each}
        </div>
        <span class="ad-counter mono">{slideIdx + 1} / {slides.length}</span>
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
    width: 208px;
    flex-shrink: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s4);
    backdrop-filter: blur(10px);
    overflow-y: auto;
  }
  .ad-rail-title {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .ad-kpi {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }
  .ad-kpi-icon {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border-radius: 8px;
    background: color-mix(in srgb, currentColor 12%, transparent);
    flex-shrink: 0;
  }
  .ad-kpi-txt {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }
  .ad-kpi-label {
    font-size: 8px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.07em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .ad-kpi-val {
    font-size: 16px;
    font-weight: 700;
    font-family: var(--font-mono);
    line-height: 1.15;
    color: var(--text-primary);
  }
  .ad-kpi-best {
    font-size: 11px;
    line-height: 1.3;
  }
  .ad-rail-sep {
    height: 1px;
    background: var(--border);
    margin: var(--s1) 0;
    flex-shrink: 0;
  }
  .ad-range-label {
    font-size: 8px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-family: var(--font-mono);
  }
  .ad-range {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .ad-range-btn {
    padding: 6px 10px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: transparent;
    color: var(--text-muted);
    font-size: 10px;
    font-weight: 600;
    font-family: var(--font-mono);
    cursor: pointer;
    text-align: left;
    transition: all 0.15s;
  }
  .ad-range-btn:hover {
    color: var(--xp);
    border-color: var(--xp);
  }
  .ad-range-btn.active {
    color: var(--xp);
    border-color: var(--xp);
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
    position: relative;
    flex: 1;
    min-height: 0;
  }
  .ad-slide {
    position: absolute;
    inset: 0;
    display: grid;
    grid-template-columns: minmax(0, 1fr) 292px;
    gap: var(--s3);
    min-height: 320px;
  }
  .ad-slide-charts {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    min-width: 0;
    min-height: 0;
  }
  .ad-hero {
    flex: 1;
    min-height: 0;
    display: flex;
  }
  .ad-hero > :global(*) {
    flex: 1;
    min-width: 0;
  }
  /* Aux tiles row — present on slides that render it. */
  .ad-aux {
    flex: 0 0 clamp(140px, 30%, 200px);
    min-height: 0;
    display: flex;
    gap: var(--s3);
  }
  .ad-aux > :global(*) {
    flex: 1;
    min-width: 0;
  }

  /* Floating edge arrows — overlay style (lightbox pattern). */
  .ad-arrow-float {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    z-index: 5;
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--surface) 82%, transparent);
    backdrop-filter: blur(8px);
    color: var(--text-secondary);
    cursor: pointer;
    opacity: 0.55;
    transition:
      opacity 0.15s,
      color 0.15s,
      border-color 0.15s,
      transform 0.15s;
  }
  .ad-arrow-float.prev {
    left: 8px;
  }
  .ad-arrow-float.next {
    right: 8px;
  }
  .ad-arrow-float:hover {
    opacity: 1;
    color: var(--xp);
    border-color: var(--xp);
    transform: translateY(-50%) scale(1.06);
  }

  .ad-foot {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--s3);
    flex-shrink: 0;
  }
  .ad-dots {
    display: flex;
    justify-content: center;
    gap: 6px;
  }
  .ad-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    border: none;
    padding: 0;
    background: var(--border);
    cursor: pointer;
    transition: all 0.15s;
  }
  .ad-dot:hover {
    background: var(--text-muted);
  }
  .ad-dot.active {
    background: var(--xp);
    transform: scale(1.25);
  }
  .ad-counter {
    font-size: 9px;
    font-weight: 700;
    color: var(--text-muted);
    letter-spacing: 0.08em;
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
    border-radius: 6px;
  }
  @keyframes ad-shimmer {
    from {
      background-position: 200% 0;
    }
    to {
      background-position: -200% 0;
    }
  }
  .ad-rail-skeleton {
    padding: var(--s4);
  }
  .sk-icon {
    width: 26px;
    height: 26px;
    border-radius: 8px;
    flex-shrink: 0;
  }
  .sk-line {
    width: 80px;
    height: 14px;
  }
  .ad-slide-skeleton {
    flex: 1;
    border-radius: var(--r);
  }
  .ad-loading-label {
    position: absolute;
    bottom: 12px;
    align-self: center;
    font-size: 10px;
    color: var(--text-muted);
    font-family: var(--font-mono);
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
    border-radius: 6px;
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

  @media (max-width: 900px) {
    .ad-root {
      flex-direction: column;
    }
    .ad-rail {
      width: 100%;
      flex-direction: row;
      flex-wrap: wrap;
      align-items: center;
      overflow-x: auto;
    }
    .ad-rail-sep {
      display: none;
    }
    .ad-range {
      flex-direction: row;
      margin-left: auto;
    }
    .ad-slide {
      position: relative;
      grid-template-columns: 1fr;
    }
    .ad-arrow-float {
      display: none;
    }
  }
</style>
