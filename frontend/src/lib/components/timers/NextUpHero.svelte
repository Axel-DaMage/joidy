<script lang="ts">
  import {
    AlarmClock,
    ArrowDownToLine,
    Flag,
    Hourglass,
    Pause,
    Play,
    Plus,
    Timer,
    X,
  } from 'lucide-svelte';
  import { t } from 'svelte-i18n';
  import { locale as localeStore } from '$lib/stores/locale';
  import { use24HourClock } from '$lib/stores/settings';
  import {
    addMinuteToTimer,
    addTimer,
    formatDurationShort,
    formatHMS,
    formatStopwatch,
    lapStopwatch,
    nextAlarm,
    nextTimer,
    now,
    pauseStopwatch,
    pauseTimer,
    removeTimer,
    startStopwatch,
    stopwatch,
    stopwatchElapsed,
  } from '$lib/stores/timers';

  type HeroKind = 'alarm' | 'timer' | 'stopwatch' | 'clock';

  /** Pick the most imminent thing on the dashboard: soonest of next alarm vs
   *  running timers; fall back to an active stopwatch, then the wall clock. */
  const kind = $derived.by((): HeroKind => {
    const alarmAt = $nextAlarm?.at ?? null;
    const timerAt = $nextTimer?.timer.endsAt ?? null;
    if (alarmAt !== null && (timerAt === null || alarmAt <= timerAt)) return 'alarm';
    if (timerAt !== null) return 'timer';
    if ($stopwatch.running || $stopwatch.baseMs > 0) return 'stopwatch';
    return 'clock';
  });

  const alarmTime = $derived.by(() => {
    if (!$nextAlarm) return '';
    return new Date($nextAlarm.at).toLocaleTimeString($localeStore, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: !$use24HourClock,
    });
  });

  const clockTime = $derived.by(() =>
    new Date($now).toLocaleTimeString($localeStore, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: !$use24HourClock,
    })
  );

  const timerProgress = $derived.by(() => {
    const tm = $nextTimer?.timer;
    if (!tm || tm.totalMs <= 0) return 0;
    return Math.max(0, Math.min(1, ($nextTimer?.remainingMs ?? 0) / tm.totalMs));
  });

  function scrollToSection(id: string) {
    document
      .getElementById(id)
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function startPomodoro() {
    addTimer($t('timers.timer.pomodoro'), 25 * 60_000, { awardXp: true });
  }
  function startBreak() {
    addTimer($t('timers.timer.shortBreak'), 5 * 60_000);
  }

  // SVG ring geometry (shared size with the timer cards).
  const R = 34;
  const CIRC = 2 * Math.PI * R;
</script>

<div class="hero card">
  <div class="hero-main">
    {#if kind === 'timer' && $nextTimer}
      <div class="hero-ring" aria-hidden="true">
        <svg viewBox="0 0 80 80">
          <circle cx="40" cy="40" r={R} class="ring-bg" />
          <circle
            cx="40"
            cy="40"
            r={R}
            class="ring-fg"
            style:stroke={$nextTimer.timer.color || null}
            stroke-dasharray={CIRC}
            stroke-dashoffset={CIRC * (1 - timerProgress)}
          />
        </svg>
      </div>
    {:else}
      <div class="hero-icon" aria-hidden="true">
        {#if kind === 'alarm'}
          <AlarmClock size={22} strokeWidth={1.6} />
        {:else if kind === 'stopwatch'}
          <Hourglass size={22} strokeWidth={1.6} />
        {:else}
          <Timer size={22} strokeWidth={1.6} />
        {/if}
      </div>
    {/if}

    <div class="hero-text">
      <span class="eyebrow">
        {#if kind === 'alarm'}
          {$t('timers.hero.nextAlarm')} · {alarmTime}
        {:else if kind === 'timer'}
          {$t('timers.hero.nextTimer')}
        {:else if kind === 'stopwatch'}
          {$t('timers.hero.stopwatchRunning')}
        {:else}
          {$t('timers.hero.clock')}
        {/if}
      </span>

      <span class="hero-time mono">
        {#if kind === 'alarm' && $nextAlarm}
          {$t('timers.hero.in', {
            values: { time: formatDurationShort($nextAlarm.at - $now) },
          })}
        {:else if kind === 'timer' && $nextTimer}
          {formatHMS($nextTimer.remainingMs)}
        {:else if kind === 'stopwatch'}
          {formatStopwatch($stopwatchElapsed)}
        {:else}
          {clockTime}
        {/if}
      </span>

      <span class="hero-sub muted">
        {#if kind === 'alarm' && $nextAlarm}
          {$nextAlarm.alarm.label || $t('timers.alert.alarmTitle')}
        {:else if kind === 'timer' && $nextTimer}
          {$nextTimer.timer.label || $t('timers.sections.timers')}
        {:else if kind === 'stopwatch'}
          {$stopwatch.running ? $t('timers.timer.running') : $t('timers.timer.paused')}
        {:else}
          {$t('timers.hero.nothingHint')}
        {/if}
      </span>
    </div>
  </div>

  <div class="hero-actions">
    {#if kind === 'timer' && $nextTimer}
      {@const tm = $nextTimer.timer}
      <button
        type="button"
        class="btn"
        title={$t('timers.timer.pause')}
        onclick={() => pauseTimer(tm.id)}
      >
        <Pause size={14} />
        {$t('timers.timer.pause')}
      </button>
      <button
        type="button"
        class="btn"
        title={$t('timers.timer.plusOne')}
        onclick={() => addMinuteToTimer(tm.id)}
      >
        <Plus size={14} />
        {$t('timers.timer.plusOne')}
      </button>
      <button
        type="button"
        class="btn btn-ghost"
        title={$t('common.delete')}
        aria-label={$t('common.delete')}
        onclick={() => removeTimer(tm.id)}
      >
        <X size={14} />
      </button>
    {:else if kind === 'alarm'}
      <button
        type="button"
        class="btn"
        onclick={() => scrollToSection('timers-section-alarms')}
      >
        <ArrowDownToLine size={14} />
        {$t('timers.sections.alarms')}
      </button>
    {:else if kind === 'stopwatch'}
      {#if $stopwatch.running}
        <button type="button" class="btn" onclick={pauseStopwatch}>
          <Pause size={14} />
          {$t('timers.stopwatch.pause')}
        </button>
        <button type="button" class="btn" onclick={lapStopwatch}>
          <Flag size={14} />
          {$t('timers.stopwatch.lap')}
        </button>
      {:else}
        <button type="button" class="btn btn-primary" onclick={startStopwatch}>
          <Play size={14} />
          {$t('timers.stopwatch.start')}
        </button>
      {/if}
    {:else}
      <button type="button" class="btn btn-primary" onclick={startPomodoro}>
        <Timer size={14} />
        {$t('timers.hero.quickPomodoro')}
      </button>
      <button type="button" class="btn" onclick={startBreak}>
        {$t('timers.hero.quickBreak')}
      </button>
    {/if}
  </div>
</div>

<style>
  .hero {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s4);
    padding: var(--s4);
    flex-wrap: wrap;
  }
  .hero-main {
    display: flex;
    align-items: center;
    gap: var(--s4);
    min-width: 0;
  }
  .hero-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 64px;
    height: 64px;
    flex-shrink: 0;
    border: 1px solid var(--border);
    border-radius: 50%;
    color: var(--xp);
    background: color-mix(in srgb, var(--xp) 8%, transparent);
  }
  .hero-ring {
    width: 64px;
    height: 64px;
    flex-shrink: 0;
  }
  .hero-ring svg {
    width: 100%;
    height: 100%;
    transform: rotate(-90deg);
  }
  .ring-bg {
    fill: none;
    stroke: var(--border);
    stroke-width: 5;
  }
  .ring-fg {
    fill: none;
    stroke: var(--xp);
    stroke-width: 5;
    stroke-linecap: round;
    transition: stroke-dashoffset 0.25s linear;
  }
  .hero-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .eyebrow {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-muted);
  }
  .hero-time {
    font-size: clamp(30px, 5vw, 42px);
    font-weight: 600;
    line-height: 1.1;
    font-variant-numeric: tabular-nums;
    color: var(--text-primary);
  }
  .hero-sub {
    font-size: 12px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .hero-actions {
    display: flex;
    align-items: center;
    gap: var(--s2);
    flex-wrap: wrap;
  }
  @media (prefers-reduced-motion: reduce) {
    .ring-fg {
      transition: none;
    }
  }
</style>
