<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { RotateCcw, SkipForward } from 'lucide-svelte';

  // ── Timezone ───────────────────────────────────────────────────────────────
  const TZ_MAP: Record<string, string> = {
    'chile':       'America/Santiago',
    'españa':      'Europe/Madrid',
    'mexico':      'America/Mexico_City',
    'méxico':      'America/Mexico_City',
    'argentina':   'America/Argentina/Buenos_Aires',
    'colombia':    'America/Bogota',
    'peru':        'America/Lima',
    'perú':        'America/Lima',
    'venezuela':   'America/Caracas',
    'ecuador':     'America/Guayaquil',
    'uruguay':     'America/Montevideo',
    'brasil':      'America/Sao_Paulo',
    'brazil':      'America/Sao_Paulo',
    'usa':         'America/New_York',
    'eeuu':        'America/New_York',
    'uk':          'Europe/London',
    'alemania':    'Europe/Berlin',
    'francia':     'Europe/Paris',
    'japon':       'Asia/Tokyo',
    'japón':       'Asia/Tokyo',
    'china':       'Asia/Shanghai',
    'australia':   'Australia/Sydney',
    'utc':         'UTC',
  };

  const TZ_PRESETS = [
    ['🇨🇱 Chile',      'America/Santiago'],
    ['🇪🇸 España',     'Europe/Madrid'],
    ['🇲🇽 México',     'America/Mexico_City'],
    ['🇦🇷 Argentina',  'America/Argentina/Buenos_Aires'],
    ['🇨🇴 Colombia',   'America/Bogota'],
    ['🇵🇪 Perú',       'America/Lima'],
    ['🇧🇷 Brasil',     'America/Sao_Paulo'],
    ['🌐 UTC',         'UTC'],
  ] as const;

  let timezone: string = 'UTC';
  let showTzPicker = false;
  let tzInput = '';
  let tzError = '';

  function initTimezone() {
    const saved = localStorage.getItem('joidy-timezone');
    if (saved) { timezone = saved; return; }
    try {
      timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch { timezone = 'UTC'; }
  }

  function setTimezone(tz: string) {
    try {
      new Intl.DateTimeFormat(undefined, { timeZone: tz });
      timezone = tz;
      localStorage.setItem('joidy-timezone', tz);
      showTzPicker = false;
      tzInput = '';
      tzError = '';
      updateClock();
    } catch {
      tzError = 'Timezone inválido';
    }
  }

  function applyTzInput() {
    const raw = tzInput.trim().toLowerCase();
    const mapped = TZ_MAP[raw];
    setTimezone(mapped ?? tzInput.trim());
  }

  // ── Clock ──────────────────────────────────────────────────────────────────
  let clockStr = '--:--:--';

  function updateClock() {
    try {
      clockStr = new Date().toLocaleTimeString('es', {
        timeZone: timezone,
        hour:     '2-digit',
        minute:   '2-digit',
        second:   '2-digit',
        hour12:   false,
      });
    } catch { clockStr = '--:--:--'; }
  }

  // ── Timer ──────────────────────────────────────────────────────────────────
  type Phase = 'work' | 'break' | 'longBreak';

  // Duration presets cycled with click
  const WORK_PRESETS  = [25, 50, 90, 15, 5];
  const BREAK_PRESETS = [5, 10, 15, 3];
  let workIdx  = 0;
  let breakIdx = 0;
  $: workMins  = WORK_PRESETS[workIdx];
  $: breakMins = BREAK_PRESETS[breakIdx];
  const longMins = 15;

  let phase: Phase = 'work';
  let running = false;
  let secondsLeft = 25 * 60;
  let pomodorosDone = 0;
  let clockInterval:  ReturnType<typeof setInterval> | null = null;
  let timerInterval:  ReturnType<typeof setInterval> | null = null;

  // Ring geometry — r=58, circ=2π×58≈364.4
  const R    = 58;
  const CIRC = 2 * Math.PI * R;

  $: totalSec    = phase === 'work' ? workMins * 60 : phase === 'break' ? breakMins * 60 : longMins * 60;
  $: progress    = secondsLeft / totalSec;
  $: dashOffset  = CIRC * (1 - progress);
  $: ringColor   = phase === 'work' ? 'var(--xp)' : 'var(--success)';
  $: mins        = String(Math.floor(secondsLeft / 60)).padStart(2, '0');
  $: secs        = String(secondsLeft % 60).padStart(2, '0');

  const PHASE_LABEL: Record<Phase, string> = {
    work: 'TRABAJO', break: 'DESCANSO', longBreak: 'DESCANSO LARGO',
  };

  function tick() {
    if (secondsLeft > 0) { secondsLeft--; }
    else { advance(); }
  }

  function advance() {
    stopTimer();
    if (phase === 'work') {
      pomodorosDone++;
      phase = pomodorosDone % 4 === 0 ? 'longBreak' : 'break';
    } else {
      phase = 'work';
    }
    secondsLeft = totalSec;
    startTimer();
  }

  function startTimer() {
    if (timerInterval) return;
    running = true;
    timerInterval = setInterval(tick, 1000);
  }

  function stopTimer() {
    if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
    running = false;
  }

  function toggle() { running ? stopTimer() : startTimer(); }

  function reset() {
    stopTimer();
    phase = 'work';
    secondsLeft = workMins * 60;
    pomodorosDone = 0;
  }

  function skip() { advance(); }

  function cycleWork() {
    if (running) return;
    workIdx = (workIdx + 1) % WORK_PRESETS.length;
    secondsLeft = workMins * 60;
  }

  function cycleBreak() {
    if (running) return;
    breakIdx = (breakIdx + 1) % BREAK_PRESETS.length;
  }

  onMount(() => {
    initTimezone();
    updateClock();
    clockInterval = setInterval(updateClock, 1000);
    secondsLeft = workMins * 60;
  });

  onDestroy(() => {
    stopTimer();
    if (clockInterval) clearInterval(clockInterval);
  });
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="pomodoro" on:keydown={(e) => e.key === 'Escape' && (showTzPicker = false)}>

  <!-- Clock row — click to pick timezone -->
  <div class="clock-row">
    {#if showTzPicker}
      <div class="tz-picker">
        <input
          class="tz-input mono"
          bind:value={tzInput}
          placeholder="Chile, Europe/Madrid, UTC..."
          on:keydown={(e) => e.key === 'Enter' && applyTzInput()}
          autofocus
        />
        {#if tzError}<span class="tz-error">{tzError}</span>{/if}
        <div class="tz-presets">
          {#each TZ_PRESETS as [label, tz]}
            <button class="tz-preset mono" on:click={() => setTimezone(tz)}>{label}</button>
          {/each}
        </div>
        <button class="tz-close" on:click={() => showTzPicker = false}>✕</button>
      </div>
    {:else}
      <!-- svelte-ignore a11y-click-events-have-key-events -->
      <span class="clock mono" on:click={() => showTzPicker = true} title="Cambiar zona horaria">
        {clockStr}
      </span>
    {/if}
  </div>

  <!-- Big ring -->
  <div class="ring-wrap">
    <svg width="150" height="150" viewBox="0 0 150 150" class="ring-svg">
      <!-- Background track -->
      <circle cx="75" cy="75" r={R} stroke="var(--border)" stroke-width="4" fill="none"/>
      <!-- Progress arc -->
      <circle cx="75" cy="75" r={R}
        stroke={ringColor}
        stroke-width="4"
        fill="none"
        stroke-linecap="round"
        stroke-dasharray={CIRC}
        stroke-dashoffset={dashOffset}
        transform="rotate(-90 75 75)"
        style="transition: stroke-dashoffset 950ms linear, stroke 400ms ease;"
      />
    </svg>

    <!-- Overlay: timer + phase + dots -->
    <div class="ring-overlay">
      <span class="timer mono">{mins}:{secs}</span>
      <span class="phase-lbl mono">{PHASE_LABEL[phase]}</span>
      <div class="pomo-dots">
        {#each Array(4) as _, i}
          <span class="pdot" class:lit={i < pomodorosDone % 4}></span>
        {/each}
      </div>
    </div>
  </div>

  <!-- Controls + duration hints — two compact rows -->
  <div class="controls-row">
    <button class="ctrl-main" class:active={running} on:click={toggle}>
      {running ? 'Pausar' : 'Iniciar'}
    </button>
    <button class="ctrl-icon" on:click={reset} title="Reiniciar"><RotateCcw size={11}/></button>
    <button class="ctrl-icon" on:click={skip}  title="Saltar"><SkipForward  size={11}/></button>
  </div>

  <div class="duration-row">
    <button class="dur-chip mono" on:click={cycleWork}  title="Cambiar duración trabajo">
      {workMins}min trabajo
    </button>
    <span class="dur-sep">·</span>
    <button class="dur-chip mono" on:click={cycleBreak} title="Cambiar descanso">
      {breakMins}min descanso
    </button>
  </div>

</div>

<style>
  .pomodoro {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 14px 0 10px;
    border-top: 1px solid var(--border-light, var(--border));
    width: 100%;
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
    color: var(--text-primary);
    letter-spacing: 0.08em;
    cursor: pointer;
    transition: color var(--t-fast);
  }
  .clock:hover { color: var(--text-secondary); }

  /* ── Timezone picker ── */
  .tz-picker {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 0 12px;
    position: relative;
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

  .tz-close {
    position: absolute;
    top: 0;
    right: 12px;
    background: none;
    border: none;
    font-size: 12px;
    color: var(--text-muted);
    cursor: pointer;
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
    font-size: 30px;
    font-weight: 300;
    color: var(--text-primary);
    line-height: 1;
    letter-spacing: 0.04em;
  }

  .phase-lbl {
    font-size: 8px;
    color: var(--text-muted);
    letter-spacing: 0.1em;
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
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--t-fast);
    min-width: 80px;
  }
  .ctrl-main:hover  { background: var(--elevated); color: var(--text-primary); }
  .ctrl-main.active { border-color: var(--xp); color: var(--xp); }
  .ctrl-main.active:hover { background: color-mix(in srgb, var(--xp) 10%, transparent); }

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

  .dur-chip {
    font-size: 9px;
    color: var(--text-muted);
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 2px;
    transition: color var(--t-fast);
  }
  .dur-chip:hover { color: var(--text-secondary); background: var(--elevated); }

  .dur-sep {
    font-size: 9px;
    color: var(--text-disabled, var(--border));
  }
</style>
