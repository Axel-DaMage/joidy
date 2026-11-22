<script lang="ts">
  import Flame from 'lucide-svelte/icons/flame';
  import Award from 'lucide-svelte/icons/award';
  import CalendarCheck from 'lucide-svelte/icons/calendar-check';
  import Target from 'lucide-svelte/icons/target';
  import ChartCard from './ChartCard.svelte';
  import CountUp from './CountUp.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { t } from 'svelte-i18n';

  // Streak + habit tile (#1499): current streak vs record, habit stats and
  // the 30-day check-in rate. `checkin_rate_30d` is already a percentage
  // (0–100) from the API — it must not be scaled again.
  type Streaks = AnalyticsOverview['streaks'];

  let { streaks }: { streaks?: Streaks } = $props();

  let current = $derived(streaks?.current_streak ?? 0);
  let record = $derived(streaks?.longest_streak ?? 0);
  let rate = $derived(Math.min(100, Math.max(0, streaks?.checkin_rate_30d ?? 0)));
  let toRecord = $derived(record > 0 ? Math.min(100, (current / record) * 100) : 0);

  const R = 34;
  const CIRC = 2 * Math.PI * R;
</script>

<ChartCard title={$t('goalsAnalytics.streakPanel.title')}>
  {#snippet icon()}<Flame size={13} />{/snippet}

  <div class="sp-body">
    <div class="sp-hero">
      <div class="sp-flame" class:lit={current > 0}><Flame size={24} /></div>
      <div class="sp-hero-text">
        <span class="sp-big"><CountUp value={current} /></span>
        <span class="sp-label">{$t('goalsAnalytics.streakPanel.current')}</span>
      </div>
    </div>

    <div class="sp-record">
      <div class="sp-record-bar"><div class="sp-record-fill" style:width="{toRecord}%"></div></div>
      <span class="sp-record-txt mono"
        >{$t('goalsAnalytics.streakPanel.toRecord', { values: { record } })}</span
      >
    </div>

    <div class="sp-grid">
      <div class="sp-item">
        <Award size={13} />
        <span class="sp-val">{record}</span>
        <span class="sp-key">{$t('goalsAnalytics.streakPanel.record')}</span>
      </div>
      <div class="sp-item">
        <Target size={13} />
        <span class="sp-val">{streaks?.active_streaks ?? 0}</span>
        <span class="sp-key">{$t('goalsAnalytics.streakPanel.active')}</span>
      </div>
      <div class="sp-item">
        <CalendarCheck size={13} />
        <span class="sp-val">{(streaks?.total_checkins ?? 0).toLocaleString()}</span>
        <span class="sp-key">{$t('goalsAnalytics.streakPanel.checkins')}</span>
      </div>
    </div>

    <div class="sp-rate">
      <svg viewBox="0 0 80 80" class="sp-ring" aria-hidden="true">
        <circle cx="40" cy="40" r={R} class="sp-ring-bg" />
        <circle
          cx="40"
          cy="40"
          r={R}
          class="sp-ring-fg"
          stroke-dasharray={CIRC}
          stroke-dashoffset={CIRC * (1 - rate / 100)}
          transform="rotate(-90 40 40)"
        />
        <text x="40" y="45" text-anchor="middle" class="sp-ring-val">{Math.round(rate)}%</text>
      </svg>
      <div class="sp-rate-txt">
        <span class="sp-rate-title">{$t('goalsAnalytics.streakPanel.rate30d')}</span>
        <span class="sp-rate-sub">{$t('goalsAnalytics.streakPanel.rateHint')}</span>
      </div>
    </div>
  </div>
</ChartCard>

<style>
  .sp-body {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-around;
    gap: var(--s2);
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
    border-radius: var(--r);
    border: 1px solid var(--border);
    color: var(--text-muted);
    flex-shrink: 0;
  }
  .sp-flame.lit {
    color: var(--today);
  }
  .sp-hero-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .sp-big {
    font-size: 30px;
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
  .sp-record {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }
  .sp-record-bar {
    height: 5px;
    border-radius: 3px;
    background: color-mix(in srgb, var(--text-primary) 8%, transparent);
    overflow: hidden;
  }
  .sp-record-fill {
    height: 100%;
    border-radius: 3px;
    background: var(--today);
    transition: width 0.6s ease;
  }
  .sp-record-txt {
    font-size: 9px;
    color: var(--text-muted);
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
    padding: var(--s2) var(--s1);
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
  }
  .sp-val {
    font-size: 17px;
    font-weight: 800;
    font-family: var(--font-mono);
    color: var(--text-primary);
    line-height: 1.1;
  }
  .sp-key {
    font-size: 8px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-family: var(--font-mono);
    color: var(--text-muted);
    text-align: center;
  }
  .sp-rate {
    display: flex;
    align-items: center;
    gap: var(--s3);
  }
  .sp-ring {
    width: 64px;
    height: 64px;
    flex-shrink: 0;
  }
  .sp-ring-bg {
    fill: none;
    stroke: color-mix(in srgb, var(--text-primary) 9%, transparent);
    stroke-width: 7;
  }
  .sp-ring-fg {
    fill: none;
    stroke: var(--xp);
    stroke-width: 7;
    stroke-linecap: round;
    transition: stroke-dashoffset 0.9s cubic-bezier(0.2, 0.7, 0.2, 1);
  }
  .sp-ring-val {
    fill: var(--text-primary);
    font-size: 15px;
    font-weight: 800;
    font-family: var(--font-mono);
  }
  .sp-rate-txt {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .sp-rate-title {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }
  .sp-rate-sub {
    font-size: 10px;
    line-height: 1.35;
    color: var(--text-muted);
  }
</style>
