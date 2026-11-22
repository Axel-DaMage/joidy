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
  import { getLocale } from '$lib/stores/locale';
  import { logger } from '$lib/utils/logger';
  import { t } from 'svelte-i18n';
  import ConsistencyHeatmap from './ConsistencyHeatmap.svelte';
  import ProductivityTrend from './ProductivityTrend.svelte';
  import SeasonalityMatrix from './SeasonalityMatrix.svelte';
  import MoodProductivity from './MoodProductivity.svelte';
  import XpSources from './XpSources.svelte';
  import GoalsOverview from './GoalsOverview.svelte';
  import GithubActivity from './GithubActivity.svelte';

  // Holistic analytics dashboard (#1499) — top stats bar + a full-width
  // carousel of chart views (replicates the dashboard module-carousel
  // pattern: {#key} + fly with a direction-aware slide).
  const SLIDES = [
    { id: 'consistency', label: 'goalsAnalytics.slides.consistency' },
    { id: 'trend', label: 'goalsAnalytics.slides.trend' },
    { id: 'seasonality', label: 'goalsAnalytics.slides.seasonality' },
    { id: 'mood', label: 'goalsAnalytics.slides.mood' },
    { id: 'sources', label: 'goalsAnalytics.slides.sources' },
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

{#snippet slideContent(id: SlideId | undefined)}
  {#if data}
    {#if id === 'consistency'}
      <ConsistencyHeatmap activity={data.daily_activity} days={rangeDays} />
    {:else if id === 'trend'}
      <ProductivityTrend activity={data.daily_activity} />
    {:else if id === 'seasonality'}
      <SeasonalityMatrix seasonality={data.seasonality} />
    {:else if id === 'mood'}
      <MoodProductivity mood={data.mood_activity} />
    {:else if id === 'sources'}
      <XpSources byType={data.xp_by_type} />
    {:else if id === 'goals'}
      <GoalsOverview goals={data.goals} streaks={data.streaks} />
    {:else if id === 'github'}
      <GithubActivity github={data.github} />
    {/if}
  {/if}
{/snippet}

<div class="ad-root">
  {#if loading}
    <div class="ad-stats ad-stats-skeleton">
      {#each [0, 1, 2, 3, 4] as i (i)}
        <div class="ad-stat">
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
    <!-- Stats top bar -->
    <div class="ad-stats">
      <div class="ad-stat">
        <Zap size={16} style="color: var(--xp)" />
        <div class="ad-stat-txt">
          <span class="ad-stat-val">{data.summary.total_xp.toLocaleString()}</span>
          <span class="ad-stat-label">{$t('goalsAnalytics.statTotalXp')}</span>
        </div>
      </div>
      <div class="ad-stat">
        <Flame size={16} style="color: var(--today)" />
        <div class="ad-stat-txt">
          <span class="ad-stat-val">{data.streaks.current_streak}</span>
          <span class="ad-stat-label">{$t('goalsAnalytics.statStreak')}</span>
        </div>
      </div>
      <div class="ad-stat">
        <CalendarCheck size={16} style="color: var(--success)" />
        <div class="ad-stat-txt">
          <span class="ad-stat-val">{data.summary.active_days}</span>
          <span class="ad-stat-label">{$t('goalsAnalytics.statActiveDays')}</span>
        </div>
      </div>
      <div class="ad-stat">
        <TrendingUp size={16} style="color: var(--link)" />
        <div class="ad-stat-txt">
          <span class="ad-stat-val">{Math.round(data.summary.avg_daily_xp)}</span>
          <span class="ad-stat-label">{$t('goalsAnalytics.statAvgXp')}</span>
        </div>
      </div>
      <div class="ad-stat">
        <Award size={16} style="color: var(--today)" />
        <div class="ad-stat-txt">
          <span class="ad-stat-val">{data.streaks.longest_streak}</span>
          <span class="ad-stat-label">{$t('goalsAnalytics.statBestStreak')}</span>
        </div>
      </div>
      <div class="ad-stat">
        <Trophy size={16} style="color: var(--xp)" />
        <div class="ad-stat-txt">
          <span class="ad-stat-val ad-stat-best">{bestDayLabel}</span>
          <span class="ad-stat-label">{$t('goalsAnalytics.statBestDay')}</span>
        </div>
      </div>

      <!-- Global analysis window — re-windows every slide (#1499) -->
      <div class="ad-range" role="group" aria-label={$t('goalsAnalytics.rangeLabel')}>
        <span class="ad-range-label">{$t('goalsAnalytics.rangeLabel')}</span>
        {#each RANGES as r (r)}
          <button
            type="button"
            class="ad-range-btn"
            class:active={rangeDays === r}
            onclick={() => setRangeDays(r)}>{r === 365 ? '1y' : `${r}d`}</button
          >
        {/each}
      </div>
    </div>

    <!-- Slide carousel -->
    <div class="ad-carousel">
      <div class="ad-nav">
        <button
          type="button"
          class="ad-arrow"
          onclick={prevSlide}
          title={$t('common.previous')}
          aria-label={$t('common.previous')}><ChevronLeft size={16} /></button
        >
        <span class="ad-slide-label mono"
          >{$t(slides[slideIdx]?.label ?? '').toUpperCase()}</span
        >
        <button
          type="button"
          class="ad-arrow"
          onclick={nextSlide}
          title={$t('common.next')}
          aria-label={$t('common.next')}><ChevronRight size={16} /></button
        >
      </div>

      <div class="ad-viewport">
        {#key slideIdx}
          <div class="ad-slide" in:fly={{ x: slideDir * 40, duration: 220, opacity: 0 }}>
            {@render slideContent(slides[slideIdx]?.id)}
          </div>
        {/key}
      </div>

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
    flex-direction: column;
    gap: var(--s3);
    width: 100%;
    min-height: 0;
  }

  /* ── Stats top bar ── */
  .ad-stats {
    display: flex;
    align-items: center;
    gap: var(--s5);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3) var(--s4);
    backdrop-filter: blur(10px);
    flex-wrap: wrap;
    flex-shrink: 0;
  }
  .ad-stat {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1;
    min-width: 120px;
  }
  .ad-stat-txt {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .ad-stat-val {
    font-size: 18px;
    font-weight: 700;
    font-family: var(--font-mono);
    line-height: 1;
    color: var(--text-primary);
  }
  .ad-stat-best {
    font-size: 13px;
    line-height: 1.3;
  }
  .ad-stat-label {
    font-size: 9px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  /* ── Global range selector ── */
  .ad-range {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-left: auto;
  }
  .ad-range-label {
    font-size: 9px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-right: 2px;
  }
  .ad-range-btn {
    padding: 3px 9px;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: transparent;
    color: var(--text-muted);
    font-size: 10px;
    font-family: var(--font-mono);
    cursor: pointer;
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
    min-height: 0;
  }
  .ad-nav {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--s4);
  }
  .ad-arrow {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }
  .ad-arrow:hover {
    color: var(--xp);
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 10%, transparent);
  }
  .ad-slide-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    color: var(--text-secondary);
    min-width: 180px;
    text-align: center;
  }
  .ad-viewport {
    position: relative;
    min-height: 0;
  }
  .ad-slide {
    width: 100%;
    min-height: 340px;
    display: flex;
  }
  .ad-slide > :global(*) {
    flex: 1;
    min-width: 0;
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
  .ad-stats-skeleton {
    min-height: 62px;
  }
  .sk-icon {
    width: 22px;
    height: 22px;
    border-radius: 50%;
  }
  .sk-line {
    width: 80px;
    height: 14px;
  }
  .ad-slide-skeleton {
    min-height: 340px;
    border-radius: var(--r);
  }
  .ad-loading-label {
    align-self: center;
    font-size: 10px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .ad-error {
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
</style>
