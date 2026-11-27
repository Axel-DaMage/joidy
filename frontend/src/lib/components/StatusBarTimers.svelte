<script lang="ts">
  // Live footer widget for the Clock engine (#1661): surfaces the most urgent
  // active item — a ringing alert, a running countdown timer or the stopwatch —
  // in the status bar, so time tracking is visible on every route. Purely
  // derived from the existing stores; the 1s tick is the shared `now` store,
  // so this costs nothing extra.
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { t } from 'svelte-i18n';
  import {
    BellRing,
    ClockPlus,
    Hourglass,
    Pause,
    Play,
    RotateCcw,
    X,
  } from 'lucide-svelte';
  import {
    activeAlert,
    dismissAlert,
    formatHMS,
    pauseStopwatch,
    pauseTimer,
    removeTimer,
    resetStopwatch,
    resumeTimer,
    snoozeAlert,
    startStopwatch,
    stopwatch,
    stopwatchElapsed,
    timers,
    timersRemaining,
    type TimerItem,
  } from '$lib/stores/timers';

  // Flattened display model so the template never has to narrow unions.
  interface WidgetView {
    kind: 'alert' | 'timer' | 'stopwatch';
    /** Paused countdown / paused stopwatch get a muted treatment. */
    paused: boolean;
    label: string;
    /** Formatted clock text ('' for a ringing alert). */
    timeText: string;
    /** Remaining fraction 0..1 — only meaningful for countdown timers. */
    progress: number;
    /** Set for countdown timers (quick actions target this id). */
    timerId: string;
    timerRunning: boolean;
    /** Alert only: true for alarms (snooze allowed), false for timers. */
    isAlarm: boolean;
  }

  // Priority order: ringing alert > running countdown (soonest first) >
  // running stopwatch > paused countdown > paused-but-elapsed stopwatch.
  // Scheduled alarms that are not ringing and finished timers never occupy
  // the widget — only running/alerting state.
  const items = $derived.by((): WidgetView[] => {
    const list: WidgetView[] = [];

    if ($activeAlert) {
      list.push({
        kind: 'alert',
        paused: false,
        label: $activeAlert.label,
        timeText: '',
        progress: 0,
        timerId: '',
        timerRunning: false,
        isAlarm: $activeAlert.kind === 'alarm',
      });
    }

    const running: { tm: TimerItem; rem: number }[] = [];
    const pausedTms: { tm: TimerItem; rem: number }[] = [];
    for (const tm of $timers) {
      const rem = $timersRemaining.get(tm.id) ?? tm.remainingMs;
      if (tm.status === 'running') running.push({ tm, rem });
      else if (tm.status === 'paused') pausedTms.push({ tm, rem });
    }
    running.sort((a, b) => a.rem - b.rem);

    const timerView = (tm: TimerItem, rem: number): WidgetView => ({
      kind: 'timer',
      paused: tm.status === 'paused',
      label: tm.label,
      timeText: formatHMS(rem),
      progress: tm.totalMs > 0 ? Math.max(0, Math.min(1, rem / tm.totalMs)) : 0,
      timerId: tm.id,
      timerRunning: tm.status === 'running',
      isAlarm: false,
    });
    for (const r of running) list.push(timerView(r.tm, r.rem));

    if ($stopwatch.running) {
      list.push({
        kind: 'stopwatch',
        paused: false,
        label: '',
        timeText: formatHMS($stopwatchElapsed),
        progress: 0,
        timerId: '',
        timerRunning: false,
        isAlarm: false,
      });
    }

    for (const p of pausedTms) list.push(timerView(p.tm, p.rem));

    if (!$stopwatch.running && $stopwatch.baseMs > 0) {
      list.push({
        kind: 'stopwatch',
        paused: true,
        label: '',
        timeText: formatHMS($stopwatchElapsed),
        progress: 0,
        timerId: '',
        timerRunning: false,
        isAlarm: false,
      });
    }

    return list;
  });

  const primary = $derived(items.length > 0 ? items[0] : null);
  const extraCount = $derived(Math.max(0, items.length - 1));

  // Mini progress ring geometry (same technique as TimersPanel, scaled down).
  const R = 6;
  const CIRC = 2 * Math.PI * R;
</script>

{#if primary}
  {@const p = primary}
  <div class="sb-timers" class:is-alert={p.kind === 'alert'} class:is-paused={p.paused}>
    <button
      type="button"
      class="sb-t-main"
      title={$t('timers.statusbar.open')}
      aria-label={$t('timers.statusbar.open')}
      onclick={() => goto(resolve('/timers'))}
    >
      {#if p.kind === 'alert'}
        <span class="sb-t-icon"><BellRing size={12} /></span>
        <span class="sb-t-label">
          {p.label ||
            (p.isAlarm ? $t('timers.alert.alarmTitle') : $t('timers.alert.timerTitle'))}
        </span>
      {:else if p.kind === 'timer'}
        <svg viewBox="0 0 16 16" class="sb-t-ring" aria-hidden="true">
          <circle cx="8" cy="8" r={R} class="sb-t-ring-bg" />
          <circle
            cx="8"
            cy="8"
            r={R}
            class="sb-t-ring-fg"
            stroke-dasharray={CIRC}
            stroke-dashoffset={CIRC * (1 - p.progress)}
          />
        </svg>
        <span class="sb-t-time mono">{p.timeText}</span>
        {#if p.label}<span class="sb-t-label">{p.label}</span>{/if}
      {:else}
        <span class="sb-t-icon"><Hourglass size={12} /></span>
        <span class="sb-t-time mono">{p.timeText}</span>
        <span class="sb-t-label">{$t('timers.tabs.stopwatch')}</span>
      {/if}
      {#if extraCount > 0}
        <span
          class="sb-t-badge"
          title={$t('timers.statusbar.moreActive', { values: { count: items.length } })}
          >+{extraCount}</span
        >
      {/if}
    </button>

    <!-- Quick actions revealed on hover/focus, matching .mini-pomo pills -->
    <div class="sb-t-actions">
      {#if p.kind === 'alert'}
        {#if p.isAlarm}
          <button
            type="button"
            class="sb-t-act"
            title={$t('timers.alert.snooze')}
            aria-label={$t('timers.alert.snooze')}
            onclick={snoozeAlert}><ClockPlus size={12} /></button
          >
        {/if}
        <button
          type="button"
          class="sb-t-act"
          title={$t('timers.alert.dismiss')}
          aria-label={$t('timers.alert.dismiss')}
          onclick={dismissAlert}><X size={12} /></button
        >
      {:else if p.kind === 'timer'}
        {#if p.timerRunning}
          <button
            type="button"
            class="sb-t-act"
            title={$t('timers.timer.pause')}
            aria-label={$t('timers.timer.pause')}
            onclick={() => pauseTimer(p.timerId)}><Pause size={12} /></button
          >
        {:else}
          <button
            type="button"
            class="sb-t-act"
            title={$t('timers.timer.resume')}
            aria-label={$t('timers.timer.resume')}
            onclick={() => resumeTimer(p.timerId)}><Play size={12} /></button
          >
        {/if}
        <button
          type="button"
          class="sb-t-act"
          title={$t('common.delete')}
          aria-label={$t('common.delete')}
          onclick={() => removeTimer(p.timerId)}><X size={12} /></button
        >
      {:else}
        {#if p.paused}
          <button
            type="button"
            class="sb-t-act"
            title={$t('timers.timer.resume')}
            aria-label={$t('timers.timer.resume')}
            onclick={startStopwatch}><Play size={12} /></button
          >
        {:else}
          <button
            type="button"
            class="sb-t-act"
            title={$t('timers.stopwatch.pause')}
            aria-label={$t('timers.stopwatch.pause')}
            onclick={pauseStopwatch}><Pause size={12} /></button
          >
        {/if}
        <button
          type="button"
          class="sb-t-act"
          title={$t('timers.stopwatch.reset')}
          aria-label={$t('timers.stopwatch.reset')}
          onclick={resetStopwatch}><RotateCcw size={12} /></button
        >
      {/if}
    </div>
  </div>
{/if}

<style>
  /* Mirrors .mini-pomo: an elevated pill in the statusbar right cluster that
     tints with --xp while something is actively running. */
  .sb-timers {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-left: 6px;
    padding: 2px 8px;
    border: 1px solid var(--xp);
    border-radius: var(--r);
    background: color-mix(in srgb, var(--xp) 5%, transparent);
    color: var(--xp);
    transition: all var(--t-normal);
  }
  .sb-timers.is-paused {
    border-color: var(--border);
    background: var(--elevated);
    color: var(--text-muted);
  }
  .sb-timers.is-alert {
    border-color: var(--error);
    background: color-mix(in srgb, var(--error) 8%, transparent);
    color: var(--error);
    animation: sb-t-alert 1.4s ease-in-out infinite;
  }
  @keyframes sb-t-alert {
    0%,
    100% {
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--error) 35%, transparent);
    }
    50% {
      box-shadow: 0 0 0 5px transparent;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .sb-timers.is-alert {
      animation: none;
    }
    .sb-t-ring-fg {
      transition: none;
    }
  }

  .sb-t-main {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0;
    border: none;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
    min-width: 0;
  }
  .sb-t-icon {
    display: flex;
    align-items: center;
    flex-shrink: 0;
  }
  .sb-t-ring {
    width: 14px;
    height: 14px;
    flex-shrink: 0;
    transform: rotate(-90deg);
  }
  .sb-t-ring-bg {
    fill: none;
    stroke: color-mix(in srgb, currentColor 25%, transparent);
    stroke-width: 2;
  }
  .sb-t-ring-fg {
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    transition: stroke-dashoffset 0.25s linear;
  }
  .sb-t-time {
    font-size: 11px;
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }
  .sb-t-label {
    font-size: 10px;
    max-width: 90px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    opacity: 0.85;
  }
  .sb-t-badge {
    font-size: 9px;
    font-weight: 700;
    font-family: var(--font-mono);
    line-height: 1;
    padding: 2px 4px;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, currentColor 45%, transparent);
  }

  /* Quick actions collapse to zero width so the pill doesn't jump on hover. */
  .sb-t-actions {
    display: flex;
    align-items: center;
    gap: 2px;
    max-width: 0;
    opacity: 0;
    overflow: hidden;
    transition:
      max-width var(--t-fast),
      opacity var(--t-fast);
  }
  .sb-timers:hover .sb-t-actions,
  .sb-timers:focus-within .sb-t-actions {
    max-width: 64px;
    opacity: 1;
  }
  .sb-t-act {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2px;
    border: none;
    border-radius: var(--r);
    background: transparent;
    color: inherit;
    cursor: pointer;
    transition:
      color var(--t-fast),
      background var(--t-fast);
  }
  .sb-t-act:hover {
    color: var(--text-primary);
    background: var(--surface-hover);
  }

  /* Narrow viewports: collapse to icon (+badge) only. */
  @media (max-width: 700px) {
    .sb-t-label,
    .sb-t-time {
      display: none;
    }
  }
</style>
