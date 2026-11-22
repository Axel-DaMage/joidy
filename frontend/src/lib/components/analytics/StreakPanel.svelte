<script lang="ts">
  import { Flame, Award, CalendarCheck, Target } from 'lucide-svelte';
  import ChartCard from './ChartCard.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { t } from 'svelte-i18n';

  // Compact habit/streak tile (#1499): current streak hero + record,
  // active streaks, check-ins and 30d check-in rate.
  type Streaks = AnalyticsOverview['streaks'];

  let { streaks }: { streaks?: Streaks } = $props();

  let rate = $derived(streaks?.checkin_rate_30d ?? null);
</script>

<ChartCard title={$t('goalsAnalytics.streakPanel.title')}>
  {#snippet icon()}<Flame size={15} />{/snippet}

  <div class="sp-body">
    <div class="sp-hero">
      <div class="sp-flame"><Flame size={26} /></div>
      <div class="sp-hero-text">
        <span class="sp-big">{streaks?.current_streak ?? 0}</span>
        <span class="sp-label">{$t('goalsAnalytics.streakPanel.current')}</span>
      </div>
    </div>

    <div class="sp-grid">
      <div class="sp-item">
        <Award size={13} />
        <span class="sp-val">{streaks?.longest_streak ?? 0}</span>
        <span class="sp-key">{$t('goalsAnalytics.streakPanel.record')}</span>
      </div>
      <div class="sp-item">
        <Target size={13} />
        <span class="sp-val">{streaks?.active_streaks ?? 0}</span>
        <span class="sp-key">{$t('goalsAnalytics.streakPanel.active')}</span>
      </div>
      <div class="sp-item">
        <CalendarCheck size={13} />
        <span class="sp-val">{streaks?.total_checkins ?? 0}</span>
        <span class="sp-key">{$t('goalsAnalytics.streakPanel.checkins')}</span>
      </div>
    </div>

    {#if rate !== null}
      <div class="sp-rate">
        <div class="sp-rate-head">
          <span>{$t('goalsAnalytics.streakPanel.rate30d')}</span>
          <span class="sp-rate-val">{Math.round(rate * 100)}%</span>
        </div>
        <div class="sp-rate-bar">
          <div class="sp-rate-fill" style:width="{Math.min(100, rate * 100)}%"></div>
        </div>
      </div>
    {/if}
  </div>
</ChartCard>

<style>
  .sp-body {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: var(--s3);
  }
  .sp-hero {
    display: flex;
    align-items: center;
    gap: var(--s3);
  }
  .sp-flame {
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--xp) 14%, transparent);
    color: var(--xp);
    flex-shrink: 0;
  }
  .sp-hero-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .sp-big {
    font-size: 26px;
    font-weight: 800;
    font-family: var(--font-mono);
    line-height: 1;
    color: var(--text-primary);
  }
  .sp-label {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .sp-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--s2);
  }
  .sp-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: var(--s2);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-muted);
  }
  .sp-val {
    font-size: 15px;
    font-weight: 700;
    font-family: var(--font-mono);
    color: var(--text-primary);
  }
  .sp-key {
    font-size: 8px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-family: var(--font-mono);
    text-align: center;
  }
  .sp-rate-head {
    display: flex;
    justify-content: space-between;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    font-family: var(--font-mono);
    margin-bottom: 4px;
  }
  .sp-rate-val {
    color: var(--xp);
  }
  .sp-rate-bar {
    height: 6px;
    border-radius: 3px;
    background: color-mix(in srgb, var(--text-primary) 8%, transparent);
    overflow: hidden;
  }
  .sp-rate-fill {
    height: 100%;
    border-radius: 3px;
    background: var(--xp);
    transition: width 0.4s ease;
  }
</style>
