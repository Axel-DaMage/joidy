<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';

  // ── Timer ──────────────────────────────────────────────────────────────────
  import {
    phase, running, secondsLeft, pomodorosDone, totalSec, workMins, breakMins,
    toggleTimer, resetTimer, skipTimer
  } from '$lib/stores/pomodoro';

  // Ring geometry — r=58, circ=2π×58≈364.4
  const R    = 58;
  const CIRC = 2 * Math.PI * R;

  $: progress    = $secondsLeft / $totalSec;
  $: dashOffset  = CIRC * (1 - progress);
  $: mins        = String(Math.floor($secondsLeft / 60)).padStart(2, '0');
  $: secs        = String($secondsLeft % 60).padStart(2, '0');

  const PHASE_LABEL: Record<string, string> = {
    work: 'TRABAJO', break: 'DESCANSO', longBreak: 'DESCANSO LARGO',
  };
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="pomodoro">

  <!-- Phase title -->
  <span class="phase-title mono">{PHASE_LABEL[$phase]}</span>

  <!-- Big ring -->
  <div class="ring-wrap">
    <svg width="150" height="150" viewBox="0 0 150 150" class="ring-svg">
      <defs>
        <linearGradient id="pomodoroRingBlend" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="var(--xp)" />
          <stop offset="52%" stop-color="var(--xp-2)" />
          <stop offset="100%" stop-color="var(--xp-3)" />
        </linearGradient>
      </defs>
      <!-- Background track -->
      <circle cx="75" cy="75" r={R} stroke="var(--border)" stroke-width="4" fill="none"/>
      <!-- Progress arc -->
      <circle cx="75" cy="75" r={R}
        stroke="url(#pomodoroRingBlend)"
        stroke-width="4"
        fill="none"
        stroke-linecap="round"
        stroke-dasharray={CIRC}
        stroke-dashoffset={dashOffset}
        transform="rotate(-90 75 75)"
        style="transition: stroke-dashoffset 950ms linear;"
      />
    </svg>

    <!-- Overlay: timer + dots only -->
    <div class="ring-overlay">
      <span class="timer mono">{mins}:{secs}</span>
      <div class="pomo-dots">
        {#each Array(4) as _, i}
          <span class="pdot" class:lit={i < $pomodorosDone % 4}></span>
        {/each}
      </div>
    </div>
  </div>

  <div class="controls-row">
    <button class="ctrl-main" class:active={$running} on:click={toggleTimer}>
      {$running ? 'Pausar' : 'Iniciar'}
    </button>
    <button class="ctrl-icon" on:click={resetTimer} title="Reiniciar"><DynamicIcon name="RotateCcw" size={11}/></button>
    <button class="ctrl-icon" on:click={skipTimer}  title="Saltar"><DynamicIcon name="SkipForward" size={11}/></button>
  </div>

  <div class="duration-row">
    <div class="dur-input-wrap" class:disabled={$running}>
      <input type="number" min="1" max="180" class="dur-input mono" bind:value={$workMins} disabled={$running}/>
      <span class="dur-label">min trabajo</span>
    </div>
    <span class="dur-sep">·</span>
    <div class="dur-input-wrap" class:disabled={$running}>
      <input type="number" min="1" max="120" class="dur-input mono" bind:value={$breakMins} disabled={$running}/>
      <span class="dur-label">min descanso</span>
    </div>
  </div>

</div>

<style>
  .pomodoro {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 14px 0 10px;
    width: 100%;
  }

  /* ── Phase title ── */
  .phase-title {
    font-size: 10px;
    font-weight: 500;
    color: var(--text-primary);
    letter-spacing: 0.14em;
  }

  /* ── Separator ── */
  .separator {
    width: 80%;
    height: 1px;
    background: var(--border-light, var(--border));
    margin: 2px 0;
  }

  /* ── Clock ── */
  .clock-row {
    width: 100%;
    display: flex;
    justify-content: center;
    min-height: 28px;
    align-items: center;
  }

  .clock {
    font-size: 22px;
    font-weight: 300;
    color: var(--text-secondary);
    letter-spacing: 0.08em;
    cursor: pointer;
    transition: color var(--t-fast);
  }
  .clock:hover { color: var(--text-primary); }

  /* ── Timezone picker ── */
  .tz-picker {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 0 12px;
  }

  .tz-input-row {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
  }

  .tz-input {
    width: 100%;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 5px 10px;
    font-size: 12px;
    color: var(--text-primary);
    outline: none;
    text-align: center;
  }
  .tz-input:focus { border-color: var(--text-muted); }
  .tz-input::placeholder { color: var(--text-muted); }

  .tz-error { font-size: 10px; color: var(--error); font-family: var(--font-mono); }

  .tz-presets {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    justify-content: center;
  }

  .tz-preset {
    padding: 2px 7px;
    font-size: 10px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .tz-preset:hover { background: var(--elevated); color: var(--text-primary); }

  .tz-preset:hover { background: var(--elevated); color: var(--text-primary); }

  .tz-close-ui {
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    font-size: 14px;
    width: 26px;
    height: 26px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    transition: all var(--t-fast);
  }
  .tz-close-ui:hover {
    background: var(--hover);
    color: var(--text-primary);
  }

  /* ── Ring ── */
  .ring-wrap {
    position: relative;
    width: 150px;
    height: 150px;
    flex-shrink: 0;
  }

  .ring-svg { display: block; }

  .ring-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
  }

  .timer {
    font-size: 32px;
    font-weight: 300;
    color: var(--text-primary);
    line-height: 1;
    letter-spacing: 0.04em;
  }

  .pomo-dots {
    display: flex;
    gap: 5px;
    margin-top: 2px;
  }

  .pdot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--border);
    transition: background var(--t-normal);
  }
  .pdot.lit { background: var(--xp); }

  /* ── Controls ── */
  .controls-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .ctrl-main {
    padding: 5px 20px;
    font-size: 12px;
    font-family: var(--font-sans);
    border: 1px solid var(--xp);
    border-radius: var(--r);
    background: var(--xp);
    color: var(--bg);
    cursor: pointer;
    transition: all var(--t-fast);
    min-width: 80px;
  }
  .ctrl-main:hover  { background: var(--xp-2); border-color: var(--xp-2); }
  .ctrl-main.active { background: var(--xp-2); border-color: var(--xp-2); color: var(--bg); }
  .ctrl-main.active:hover { background: var(--xp-3); border-color: var(--xp-3); }

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
  .ctrl-icon:hover { color: var(--text-secondary); background: var(--elevated); }

  /* ── Duration hints ── */
  .duration-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .dur-input-wrap {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 0 4px;
    border-radius: 2px;
    transition: background var(--t-fast);
  }
  .dur-input-wrap:not(.disabled):hover { background: var(--elevated); }
  .dur-input-wrap.disabled { opacity: 0.4; }

  .dur-input {
    width: 24px;
    background: transparent;
    border: none;
    color: var(--text-primary);
    font-size: 11px;
    outline: none;
    text-align: right;
    appearance: textfield;
    -moz-appearance: textfield;
  }
  .dur-input::-webkit-outer-spin-button,
  .dur-input::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }
  .dur-input:disabled { cursor: not-allowed; }

  .dur-label {
    font-size: 9px;
    color: var(--text-muted);
    transition: color var(--t-fast);
  }
  .dur-input-wrap:not(.disabled):hover .dur-label { color: var(--text-secondary); }

  .dur-sep {
    font-size: 9px;
    color: var(--text-disabled, var(--border));
  }
</style>
