<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { Settings, RotateCcw, SkipForward } from 'lucide-svelte';

  // ── Clock ──────────────────────────────────────────────────────────────────
  let clockStr = '';
  function updateClock() {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    clockStr = `${h}:${m}`;
  }

  // ── Settings ───────────────────────────────────────────────────────────────
  let workMins  = 25;
  let breakMins = 5;
  let longMins  = 15;
  let showSettings = false;

  // ── Timer state ────────────────────────────────────────────────────────────
  type Phase = 'work' | 'break' | 'longBreak';

  let phase: Phase = 'work';
  let running  = false;
  let secondsLeft = workMins * 60;
  let pomodorosDone = 0;
  let interval: ReturnType<typeof setInterval> | null = null;

  // SVG progress ring — r=28, circumference = 2π*28 ≈ 175.9
  const R = 28;
  const CIRC = 2 * Math.PI * R;

  $: totalSeconds = phase === 'work' ? workMins * 60
                  : phase === 'break' ? breakMins * 60
                  : longMins * 60;
  $: progress     = secondsLeft / totalSeconds;        // 1 → 0
  $: dashOffset   = CIRC * (1 - progress);

  $: mins = String(Math.floor(secondsLeft / 60)).padStart(2, '0');
  $: secs = String(secondsLeft % 60).padStart(2, '0');

  const PHASE_LABELS: Record<Phase, string> = {
    work:      'TRABAJO',
    break:     'DESCANSO',
    longBreak: 'DESCANSO LARGO',
  };

  function tick() {
    if (secondsLeft > 0) {
      secondsLeft--;
    } else {
      advance();
    }
  }

  function advance() {
    stop();
    if (phase === 'work') {
      pomodorosDone++;
      phase = pomodorosDone % 4 === 0 ? 'longBreak' : 'break';
    } else {
      phase = 'work';
    }
    secondsLeft = totalSeconds;
    // Auto-start next phase
    start();
  }

  function start() {
    if (interval) return;
    running  = true;
    interval = setInterval(tick, 1000);
  }

  function stop() {
    if (interval) { clearInterval(interval); interval = null; }
    running = false;
  }

  function toggle() { running ? stop() : start(); }

  function reset() {
    stop();
    phase       = 'work';
    secondsLeft = workMins * 60;
    pomodorosDone = 0;
  }

  function skip() { advance(); }

  // Rebuild timer when settings change (only if stopped)
  function applySettings() {
    if (!running) secondsLeft = (phase === 'work' ? workMins : phase === 'break' ? breakMins : longMins) * 60;
    showSettings = false;
  }

  // Clock tick every 30s is enough
  let clockInterval: ReturnType<typeof setInterval>;
  onMount(() => {
    updateClock();
    clockInterval = setInterval(updateClock, 30000);
  });

  onDestroy(() => {
    stop();
    clearInterval(clockInterval);
  });
</script>

<div class="pomodoro-widget">
  <!-- Digital clock -->
  <div class="clock mono">{clockStr}</div>

  <!-- Ring + countdown -->
  <div class="ring-area">
    <svg width="80" height="80" viewBox="0 0 80 80" class="ring-svg">
      <!-- Background track -->
      <circle cx="40" cy="40" r={R}
        stroke="var(--border)" stroke-width="3" fill="none"/>
      <!-- Progress arc -->
      <circle cx="40" cy="40" r={R}
        stroke={phase === 'work' ? 'var(--xp)' : 'var(--success)'}
        stroke-width="3"
        fill="none"
        stroke-linecap="round"
        stroke-dasharray={CIRC}
        stroke-dashoffset={dashOffset}
        transform="rotate(-90 40 40)"
        style="transition: stroke-dashoffset 900ms linear, stroke 400ms ease;"
      />
      <!-- Pomo dots (up to 4) -->
      {#each Array(4) as _, i}
        <circle
          cx={40 + 22 * Math.cos((i * 90 - 45) * Math.PI / 180)}
          cy={40 + 22 * Math.sin((i * 90 - 45) * Math.PI / 180)}
          r="2"
          fill={i < pomodorosDone % 4 ? 'var(--xp)' : 'var(--border)'}
          style="transition: fill 300ms ease;"
        />
      {/each}
    </svg>

    <div class="countdown-overlay">
      <span class="countdown mono">{mins}:{secs}</span>
      <span class="phase-label mono">{PHASE_LABELS[phase]}</span>
    </div>
  </div>

  <!-- Controls -->
  <div class="controls">
    <button
      class="ctrl-btn primary"
      class:active={running}
      on:click={toggle}
    >
      {running ? 'Pausar' : 'Iniciar'}
    </button>

    <button class="ctrl-icon" on:click={reset} title="Reiniciar">
      <RotateCcw size={12} />
    </button>

    <button class="ctrl-icon" on:click={skip} title="Saltar fase">
      <SkipForward size={12} />
    </button>

    <button
      class="ctrl-icon"
      class:active={showSettings}
      on:click={() => showSettings = !showSettings}
      title="Configurar"
    >
      <Settings size={12} />
    </button>
  </div>

  <!-- Settings panel -->
  {#if showSettings}
    <div class="settings-panel">
      <label class="setting-row">
        <span class="mono">trabajo</span>
        <input type="number" min="1" max="60" bind:value={workMins} class="num-input mono"/>
        <span class="mono unit">min</span>
      </label>
      <label class="setting-row">
        <span class="mono">descanso</span>
        <input type="number" min="1" max="30" bind:value={breakMins} class="num-input mono"/>
        <span class="mono unit">min</span>
      </label>
      <label class="setting-row">
        <span class="mono">largo</span>
        <input type="number" min="5" max="60" bind:value={longMins} class="num-input mono"/>
        <span class="mono unit">min</span>
      </label>
      <button class="apply-btn mono" on:click={applySettings}>aplicar</button>
    </div>
  {/if}
</div>

<style>
  .pomodoro-widget {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 12px 0 8px;
    border-top: 1px solid var(--border-light, var(--border));
    width: 100%;
  }

  /* ── Clock ── */
  .clock {
    font-size: 28px;
    font-weight: 300;
    color: var(--text-primary);
    letter-spacing: 0.06em;
    line-height: 1;
  }

  /* ── Ring ── */
  .ring-area {
    position: relative;
    width: 80px;
    height: 80px;
  }

  .ring-svg { display: block; }

  .countdown-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1px;
  }

  .countdown {
    font-size: 15px;
    color: var(--text-primary);
    line-height: 1;
  }

  .phase-label {
    font-size: 7px;
    color: var(--text-muted);
    letter-spacing: 0.06em;
  }

  /* ── Controls ── */
  .controls {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .ctrl-btn {
    padding: 4px 14px;
    font-size: 11px;
    font-family: var(--font-sans);
    border-radius: var(--r);
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .ctrl-btn:hover  { background: var(--elevated); color: var(--text-primary); }
  .ctrl-btn.active { border-color: var(--xp); color: var(--xp); }
  .ctrl-btn.active:hover { background: color-mix(in srgb, var(--xp) 10%, transparent); }

  .ctrl-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .ctrl-icon:hover  { color: var(--text-secondary); background: var(--elevated); }
  .ctrl-icon.active { border-color: var(--text-muted); color: var(--text-secondary); }

  /* ── Settings panel ── */
  .settings-panel {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    width: 160px;
  }

  .setting-row {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    color: var(--text-secondary);
    cursor: default;
  }

  .setting-row span:first-child { flex: 1; }

  .num-input {
    width: 36px;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: 2px;
    padding: 2px 4px;
    font-size: 11px;
    color: var(--text-primary);
    text-align: right;
    outline: none;
  }
  .num-input:focus { border-color: var(--text-muted); }

  .unit { color: var(--text-muted); }

  .apply-btn {
    align-self: flex-end;
    padding: 3px 10px;
    font-size: 10px;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .apply-btn:hover { border-color: var(--text-muted); color: var(--text-primary); }
</style>
