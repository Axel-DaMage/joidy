<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { use24HourClock } from '$lib/stores/settings';

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
        hour:     $use24HourClock ? '2-digit' : 'numeric',
        minute:   '2-digit',
        second:   '2-digit',
        hour12:   !$use24HourClock,
      });
    } catch { clockStr = '--:--:--'; }
  }

  let clockInterval: ReturnType<typeof setInterval> | null = null;

  onMount(() => {
    initTimezone();
    updateClock();
    clockInterval = setInterval(updateClock, 1000);
  });

  onDestroy(() => {
    if (clockInterval) clearInterval(clockInterval);
  });

  $: $use24HourClock, updateClock();
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="time-widget" on:keydown={(e) => e.key === 'Escape' && (showTzPicker = false)}>
  <div class="clock-row">
    {#if showTzPicker}
      <div class="tz-picker">
        <div class="tz-input-row">
          <input
            class="tz-input mono"
            bind:value={tzInput}
            placeholder="Chile, Europe/Madrid, UTC..."
            on:keydown={(e) => e.key === 'Enter' && applyTzInput()}
            autofocus
          />
          <button class="tz-close-ui" on:click={() => showTzPicker = false} title="Cerrar">✕</button>
        </div>
        {#if tzError}<span class="tz-error">{tzError}</span>{/if}
        <div class="tz-presets">
          {#each TZ_PRESETS as [label, tz]}
            <button class="tz-preset mono" on:click={() => setTimezone(tz)}>{label}</button>
          {/each}
        </div>
      </div>
    {:else}
      <!-- svelte-ignore a11y-click-events-have-key-events -->
      <span class="clock mono" on:click={() => showTzPicker = true} title="Cambiar zona horaria">
        {clockStr}
      </span>
    {/if}
  </div>
</div>

<style>
  .time-widget {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    padding: 10px 0;
    border-top: 1px solid var(--border-light, var(--border));
    border-bottom: 1px solid var(--border-light, var(--border));
  }

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
  .clock:hover { color: var(--xp); }

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
  .tz-input:focus { border-color: var(--xp-2); }
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
  .tz-preset:hover {
    border-color: color-mix(in srgb, var(--xp) 45%, var(--border));
    color: var(--xp);
  }

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
    border-color: color-mix(in srgb, var(--xp-2) 45%, var(--border));
    color: var(--xp-2);
  }
</style>
