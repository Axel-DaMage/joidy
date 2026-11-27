<script lang="ts">
  import RotateCcw from 'lucide-svelte/icons/rotate-ccw';
  import SkipForward from 'lucide-svelte/icons/skip-forward';
  import TimerIcon from 'lucide-svelte/icons/timer';
  import Crosshair from 'lucide-svelte/icons/crosshair';
  import Play from 'lucide-svelte/icons/play';
  import Square from 'lucide-svelte/icons/square';
  import {
    phase,
    running,
    secondsLeft,
    totalSec,
    pomodorosDone,
    workMins,
    breakMins,
    toggleTimer,
    resetTimer,
    skipTimer,
  } from '$lib/stores/pomodoro';
  import {
    isActive as focusActive,
    focusSession,
    config as focusConfig,
    updateConfig,
    startFocusMode,
    stopFocusMode,
  } from '$lib/stores/focusMode';
  import { clockStyle } from '$lib/stores/settings';
  import { getTimerParts } from '$lib/utils/clock';
  import ClockDisplay from '$lib/components/clock/ClockDisplay.svelte';
  import { t } from 'svelte-i18n';

  /**
   * Execution-mode detail card: live pomodoro timer + focus-session status,
   * with the same duration/config controls the dashboard exposes (#ejecución).
   */

  const R = 42;
  const CIRC = 2 * Math.PI * R;

  let progress = $derived($secondsLeft / $totalSec);
  let dashOffset = $derived(CIRC * (1 - progress));
  let timerParts = $derived(getTimerParts($secondsLeft));

  const PHASE_LABEL_KEYS: Record<string, string> = {
    work: 'executionPage.phase.work',
    break: 'executionPage.phase.break',
    longBreak: 'executionPage.phase.longBreak',
  };

  // Focus session elapsed — ticks once per second only while a session is
  // active so the readout stays live without an always-on interval.
  let now = $state(Date.now());
  $effect(() => {
    if (!$focusActive) return;
    const id = setInterval(() => (now = Date.now()), 1000);
    return () => clearInterval(id);
  });

  let focusElapsedSec = $derived(
    $focusActive && $focusSession.startTime !== null
      ? Math.max(0, Math.floor((now - $focusSession.startTime) / 1000))
      : 0
  );
  let focusElapsedLabel = $derived(
    `${String(Math.floor(focusElapsedSec / 60)).padStart(2, '0')}:${String(
      focusElapsedSec % 60
    ).padStart(2, '0')}`
  );

  // Live XP estimate — mirrors stopFocusMode()'s award formula.
  let focusXpEstimate = $derived.by(() => {
    if (!$focusActive || $focusSession.startTime === null) return 0;
    const elapsedMin = Math.max(1, Math.round(focusElapsedSec / 60));
    let xp = Math.min(elapsedMin, $focusSession.duration || $focusConfig.duration);
    if ($running && xp < 5) xp = 5;
    return xp;
  });

  // Focus config inputs — local state so typing doesn't fight the store;
  // committed on change.
  let fDur = $state(25);
  let fBrk = $state(5);
  let fCyc = $state(4);
  $effect(() => {
    const c = $focusConfig;
    fDur = c.duration;
    fBrk = c.breakDuration;
    fCyc = c.cyclesBeforeLongBreak;
  });

  function commitFocusConfig() {
    updateConfig({
      duration: Number(fDur),
      breakDuration: Number(fBrk),
      cyclesBeforeLongBreak: Number(fCyc),
    });
  }

  function toggleFocus() {
    if ($focusActive) {
      stopFocusMode();
    } else {
      startFocusMode();
    }
  }
</script>

<section class="card exec-timer-card" aria-label={$t('executionPage.timerTitle')}>
  <header class="card-head">
    <TimerIcon size={13} />
    <span class="card-title">{$t('executionPage.timerTitle')}</span>
    <span class="phase-chip mono">{$t(PHASE_LABEL_KEYS[$phase] ?? 'executionPage.phase.work')}</span>
  </header>

  <div class="timer-body">
    {#if $clockStyle === 'circular'}
      <div class="ring-wrap">
        <ClockDisplay mode="timer" {progress} {...timerParts} />
        <div class="ring-overlay dots-overlay">
          <div
            class="pomo-dots"
            role="img"
            aria-label={$t('widgets.pomodorosDone', {
              values: { done: $pomodorosDone % 4, total: 4 },
            })}
          >
            {#each Array(4) as _, i}
              <span class="pdot" class:lit={i < $pomodorosDone % 4} aria-hidden="true"></span>
            {/each}
          </div>
        </div>
      </div>
    {:else}
      <div class="ring-wrap">
        <svg viewBox="0 0 120 120" class="ring-svg" aria-hidden="true" focusable="false">
          <defs>
            <linearGradient id="execRingBlend" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="var(--xp)" />
              <stop offset="52%" stop-color="var(--xp-2)" />
              <stop offset="100%" stop-color="var(--xp-3)" />
            </linearGradient>
          </defs>
          <circle cx="60" cy="60" r={R} stroke="var(--border)" stroke-width="6" fill="none" />
          <circle
            cx="60"
            cy="60"
            r={R}
            stroke="url(#execRingBlend)"
            stroke-width="6"
            fill="none"
            stroke-linecap="round"
            stroke-dasharray={CIRC}
            stroke-dashoffset={dashOffset}
            transform="rotate(-90 60 60)"
            style="transition: stroke-dashoffset 950ms linear;"
          />
        </svg>
        <div class="ring-overlay">
          <span class="timer"><ClockDisplay mode="timer" {progress} {...timerParts} /></span>
          <div
            class="pomo-dots"
            role="img"
            aria-label={$t('widgets.pomodorosDone', {
              values: { done: $pomodorosDone % 4, total: 4 },
            })}
          >
            {#each Array(4) as _, i}
              <span class="pdot" class:lit={i < $pomodorosDone % 4} aria-hidden="true"></span>
            {/each}
          </div>
        </div>
      </div>
    {/if}

    <div class="controls-row">
      <button class="ctrl-main" class:active={$running} onclick={toggleTimer}>
        {$running ? $t('widgets.pause') : $t('widgets.start')}
      </button>
      <button
        class="ctrl-icon"
        onclick={resetTimer}
        title={$t('widgets.reset')}
        aria-label={$t('widgets.reset')}><RotateCcw size={12} /></button
      >
      <button
        class="ctrl-icon"
        onclick={skipTimer}
        title={$t('widgets.skip')}
        aria-label={$t('widgets.skip')}><SkipForward size={12} /></button
      >
    </div>

    <div class="duration-row">
      <div class="dur-input-wrap" class:disabled={$running}>
        <input
          type="number"
          min="1"
          max="180"
          class="dur-input mono"
          bind:value={$workMins}
          disabled={$running}
          aria-label={$t('widgets.workMinutes')}
        />
        <span class="dur-label" aria-hidden="true">{$t('executionPage.minutesShort')}</span>
      </div>
      <span class="dur-sep" aria-hidden="true">·</span>
      <div class="dur-input-wrap" class:disabled={$running}>
        <input
          type="number"
          min="1"
          max="120"
          class="dur-input mono"
          bind:value={$breakMins}
          disabled={$running}
          aria-label={$t('widgets.breakMinutes')}
        />
        <span class="dur-label" aria-hidden="true">{$t('executionPage.breakShort')}</span>
      </div>
    </div>
  </div>

  <div class="focus-block">
    <div class="focus-head">
      <Crosshair size={13} />
      <span class="card-title">{$t('executionPage.focusTitle')}</span>
      {#if $focusActive}
        <span class="focus-live mono" title={$t('executionPage.focusXpHint', { values: { xp: focusXpEstimate } })}>
          +{focusXpEstimate} XP
        </span>
      {/if}
    </div>

    {#if $focusActive}
      <div class="focus-session">
        <span class="focus-elapsed mono">{focusElapsedLabel}</span>
        <span class="focus-meta caption">
          {$t('executionPage.focusOf', { values: { minutes: $focusSession.duration || $focusConfig.duration } })}
        </span>
      </div>
      <button class="btn btn-ghost focus-stop" onclick={() => stopFocusMode()}>
        <Square size={12} />
        {$t('executionPage.focusStop')}
      </button>
    {:else}
      <button class="btn focus-start" onclick={toggleFocus}>
        <Play size={12} />
        {$t('executionPage.focusStart')}
      </button>

      <div class="focus-config">
        <label class="cfg-field">
          <span class="cfg-label">{$t('executionPage.focusCfgWork')}</span>
          <input
            type="number"
            min="1"
            max="180"
            class="dur-input mono"
            bind:value={fDur}
            onchange={commitFocusConfig}
          />
        </label>
        <label class="cfg-field">
          <span class="cfg-label">{$t('executionPage.focusCfgBreak')}</span>
          <input
            type="number"
            min="1"
            max="120"
            class="dur-input mono"
            bind:value={fBrk}
            onchange={commitFocusConfig}
          />
        </label>
        <label class="cfg-field">
          <span class="cfg-label">{$t('executionPage.focusCfgCycles')}</span>
          <input
            type="number"
            min="1"
            max="20"
            class="dur-input mono"
            bind:value={fCyc}
            onchange={commitFocusConfig}
          />
        </label>
      </div>
      <p class="hint">{$t('executionPage.focusCfgHint')}</p>
    {/if}
  </div>
</section>

<style>
  .exec-timer-card {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    padding: var(--s2) var(--s3) var(--s3);
  }

  .card-head,
  .focus-head {
    display: flex;
    align-items: center;
    gap: var(--s2);
    color: var(--text-muted);
  }

  .card-title {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-secondary);
  }

  .phase-chip {
    margin-left: auto;
    font-size: 10px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
    border: 1px solid var(--border);
    color: var(--xp);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .timer-body {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--s2);
  }

  .ring-wrap {
    position: relative;
    width: 96px;
    height: 96px;
    flex-shrink: 0;
  }

  .ring-svg {
    display: block;
    width: 100%;
    height: 100%;
  }

  .ring-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
  }

  .ring-overlay.dots-overlay {
    justify-content: flex-end;
    padding-bottom: 22px;
  }

  .timer {
    font-size: 20px;
    font-weight: 300;
    color: var(--text-primary);
    line-height: 1;
    letter-spacing: 0.04em;
  }

  .ring-overlay :global(.clock-frame.mode-timer) {
    min-width: 0;
  }
  .ring-overlay :global(.seg-ghost) {
    display: none;
  }

  .pomo-dots {
    display: flex;
    gap: 5px;
  }

  .pdot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: transparent;
    border: 1px solid var(--border);
    transition: all var(--t-normal);
  }
  .pdot.lit {
    background: var(--xp);
    border-color: var(--xp);
    transform: scale(1.2);
  }

  .controls-row {
    display: flex;
    align-items: center;
    gap: var(--s1_5);
  }

  .ctrl-main {
    padding: 5px 18px;
    font-size: 12px;
    font-family: var(--font-sans);
    border: 1px solid var(--xp);
    border-radius: var(--r);
    background: var(--xp);
    color: var(--xp-contrast-text, var(--bg));
    cursor: pointer;
    transition: all var(--t-fast);
    min-width: 72px;
  }
  .ctrl-main:hover {
    background: var(--xp-2);
    border-color: var(--xp-2);
  }
  .ctrl-main.active {
    background: var(--xp-2);
    border-color: var(--xp-2);
  }
  .ctrl-main.active:hover {
    background: var(--xp-3);
    border-color: var(--xp-3);
  }

  .ctrl-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .ctrl-icon:hover {
    color: var(--text-secondary);
    background: var(--elevated);
  }

  .duration-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--s1_5);
  }

  .dur-input-wrap {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 0 4px;
    border-radius: 2px;
    transition: background var(--t-fast);
  }
  .dur-input-wrap:not(.disabled):hover {
    background: var(--elevated);
  }
  .dur-input-wrap.disabled {
    opacity: 0.4;
  }

  .dur-input {
    width: 26px;
    background: transparent;
    border: none;
    color: var(--text-primary);
    font-size: 11px;
    outline: none;
    text-align: right;
    appearance: textfield;
    -moz-appearance: textfield;
  }
  .dur-input:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 2px;
  }
  .dur-input::-webkit-outer-spin-button,
  .dur-input::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }
  .dur-input:disabled {
    cursor: not-allowed;
  }

  .dur-label {
    font-size: 9px;
    color: var(--text-muted);
  }

  .dur-sep {
    font-size: 9px;
    color: var(--text-muted);
  }

  /* ── Focus block ─────────────────────────────────────────────────────── */
  .focus-block {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    padding-top: var(--s2);
    border-top: 1px solid var(--border-light);
  }

  .focus-live {
    margin-left: auto;
    font-size: 11px;
    font-weight: 600;
    color: var(--xp);
  }

  .focus-session {
    display: flex;
    align-items: baseline;
    gap: var(--s2);
  }

  .focus-elapsed {
    font-size: 22px;
    font-weight: 300;
    color: var(--text-primary);
    line-height: 1;
  }

  .focus-meta {
    color: var(--text-muted);
  }

  .focus-start,
  .focus-stop {
    align-self: stretch;
    justify-content: center;
    display: inline-flex;
    align-items: center;
    gap: var(--s1_5);
    font-size: 12px;
  }

  .focus-start {
    border-color: var(--xp);
    color: var(--xp);
  }
  .focus-start:hover {
    background: color-mix(in srgb, var(--xp) 10%, transparent);
  }

  .focus-config {
    display: flex;
    gap: var(--s2);
  }

  .cfg-field {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .cfg-label {
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .cfg-field .dur-input {
    width: 100%;
    text-align: left;
    font-size: 12px;
    padding: 4px 6px;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
  }

  .hint {
    margin: 0;
    font-size: 10px;
    color: var(--text-muted);
    line-height: 1.5;
  }
</style>
