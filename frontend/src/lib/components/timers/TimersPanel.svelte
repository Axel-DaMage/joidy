<script lang="ts">
  import { Play, Pause, RotateCcw, Plus, X, Timer } from 'lucide-svelte';
  import { t } from 'svelte-i18n';
  import {
    addMinuteToTimer,
    addTimer,
    formatHMS,
    pauseTimer,
    removeTimer,
    resetTimer,
    resumeTimer,
    timers,
    timersRemaining,
    type TimerItem,
  } from '$lib/stores/timers';

  const PRESETS = [1, 5, 10, 15, 25, 30];

  let hours = 0;
  let minutes = 5;
  let seconds = 0;
  let label = '';

  function durationMs(): number {
    return ((hours || 0) * 3600 + (minutes || 0) * 60 + (seconds || 0)) * 1000;
  }

  function startCustom() {
    const ms = durationMs();
    if (ms < 1000) return;
    addTimer(label.trim(), ms);
    label = '';
  }

  function startPreset(mins: number) {
    addTimer(label.trim() || `${mins} min`, mins * 60_000);
    label = '';
  }

  function progress(tm: TimerItem, remaining: number): number {
    if (tm.totalMs <= 0) return 0;
    return Math.max(0, Math.min(1, remaining / tm.totalMs));
  }

  // SVG ring geometry
  const R = 34;
  const CIRC = 2 * Math.PI * R;
</script>

<div class="timers-panel">
  <div class="new-timer card">
    <div class="presets">
      {#each PRESETS as m}
        <button type="button" class="btn-ghost preset" onclick={() => startPreset(m)}
          >{$t('timers.timer.presetMins', { values: { minutes: m } })}</button
        >
      {/each}
    </div>
    <div class="custom-row">
      <div class="hms">
        <label class="hms-field">
          <input
            class="input mono"
            type="number"
            min="0"
            max="23"
            bind:value={hours}
            aria-label={$t('timers.timer.hours')}
          />
          <span class="muted">{$t('timers.timer.hoursShort')}</span>
        </label>
        <label class="hms-field">
          <input
            class="input mono"
            type="number"
            min="0"
            max="59"
            bind:value={minutes}
            aria-label={$t('timers.timer.minutes')}
          />
          <span class="muted">{$t('timers.timer.minutesShort')}</span>
        </label>
        <label class="hms-field">
          <input
            class="input mono"
            type="number"
            min="0"
            max="59"
            bind:value={seconds}
            aria-label={$t('timers.timer.seconds')}
          />
          <span class="muted">{$t('timers.timer.secondsShort')}</span>
        </label>
      </div>
      <input
        class="input grow"
        type="text"
        maxlength="80"
        placeholder={$t('timers.timer.labelPlaceholder')}
        bind:value={label}
        onkeydown={(e) => e.key === 'Enter' && startCustom()}
      />
      <button
        type="button"
        class="btn btn-primary"
        disabled={durationMs() < 1000}
        onclick={startCustom}
      >
        <Play size={14} />
        {$t('timers.timer.start')}
      </button>
    </div>
  </div>

  {#if $timers.length === 0}
    <div class="empty card">
      <Timer size={28} strokeWidth={1.5} />
      <p class="muted">{$t('timers.timer.empty')}</p>
    </div>
  {:else}
    <div class="timer-grid">
      {#each $timers as tm (tm.id)}
        {@const remaining = $timersRemaining.get(tm.id) ?? tm.remainingMs}
        <div class="timer-card card" class:done={tm.status === 'done'}>
          <button
            type="button"
            class="close"
            aria-label={$t('common.delete')}
            onclick={() => removeTimer(tm.id)}><X size={13} /></button
          >
          <div class="ring-wrap">
            <svg viewBox="0 0 80 80" class="ring" aria-hidden="true">
              <circle cx="40" cy="40" r={R} class="ring-bg" />
              <circle
                cx="40"
                cy="40"
                r={R}
                class="ring-fg"
                class:finished={tm.status === 'done'}
                stroke-dasharray={CIRC}
                stroke-dashoffset={CIRC * (1 - progress(tm, remaining))}
              />
            </svg>
            <span class="ring-time mono">{formatHMS(remaining)}</span>
          </div>
          {#if tm.label}<span class="timer-label">{tm.label}</span>{/if}
          <div class="timer-actions">
            {#if tm.status === 'running'}
              <button
                type="button"
                class="btn-icon"
                aria-label={$t('timers.timer.pause')}
                title={$t('timers.timer.pause')}
                onclick={() => pauseTimer(tm.id)}><Pause size={14} /></button
              >
            {:else if tm.status === 'paused'}
              <button
                type="button"
                class="btn-icon"
                aria-label={$t('timers.timer.resume')}
                title={$t('timers.timer.resume')}
                onclick={() => resumeTimer(tm.id)}><Play size={14} /></button
              >
            {/if}
            <button
              type="button"
              class="btn-icon"
              aria-label={$t('timers.timer.plusOne')}
              title={$t('timers.timer.plusOne')}
              onclick={() => addMinuteToTimer(tm.id)}><Plus size={14} /></button
            >
            <button
              type="button"
              class="btn-icon"
              aria-label={$t('timers.timer.reset')}
              title={$t('timers.timer.reset')}
              onclick={() => resetTimer(tm.id)}><RotateCcw size={14} /></button
            >
          </div>
          {#if tm.status === 'done'}
            <span class="done-tag">{$t('timers.timer.done')}</span>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .timers-panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .new-timer {
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .presets {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .preset {
    padding: 6px 12px;
    font-size: 12px;
    border: 1px solid var(--border);
    border-radius: 999px;
  }
  .custom-row {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }
  .hms {
    display: flex;
    gap: 6px;
  }
  .hms-field {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .hms-field input {
    width: 56px;
    text-align: center;
  }
  .hms-field span {
    font-size: 11px;
  }
  .grow {
    flex: 1;
    min-width: 120px;
  }
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 40px 20px;
    color: var(--text-muted);
  }
  .timer-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 10px;
  }
  .timer-card {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 14px 10px 12px;
  }
  .timer-card.done {
    border-color: var(--accent);
    animation: donePulse 1.2s ease-in-out infinite;
  }
  @keyframes donePulse {
    0%,
    100% {
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent) 40%, transparent);
    }
    50% {
      box-shadow: 0 0 0 6px transparent;
    }
  }
  .close {
    position: absolute;
    top: 6px;
    right: 6px;
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
  }
  .close:hover {
    color: var(--danger, #ef4444);
  }
  .ring-wrap {
    position: relative;
    width: 80px;
    height: 80px;
  }
  .ring {
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
    stroke: var(--accent);
    stroke-width: 5;
    stroke-linecap: round;
    transition: stroke-dashoffset 0.25s linear;
  }
  .ring-fg.finished {
    stroke: var(--success, #22c55e);
  }
  .ring-time {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .timer-label {
    font-size: 11px;
    color: var(--text-muted);
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .timer-actions {
    display: flex;
    gap: 2px;
  }
  .done-tag {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--success, #22c55e);
  }
</style>
