<script lang="ts">
  import type { ClockStyleProps } from './types';

  let {
    hours,
    minutes,
    seconds,
    ampm = null,
    h = 0,
    m = 0,
    s = 0,
    mode = 'clock',
    progress = 1,
    size = 'md',
  }: ClockStyleProps = $props();

  // Pixel footprint for the analog dial (clock mode). Timer mode fills its
  // host container instead (the pomodoro/focus ring-wrap provides the box).
  const PX: Record<string, number> = { sm: 64, md: 100, lg: 150 };
  let px = $derived(PX[size] ?? PX.md);

  let hourDeg = $derived(((h % 12) + m / 60) * 30);
  let minDeg = $derived((m + s / 60) * 6);
  let secDeg = $derived(s * 6);

  const R = 46;
  const CIRC = 2 * Math.PI * R;
  let clamped = $derived(Math.min(1, Math.max(0, progress)));
  let dashOffset = $derived(CIRC * (1 - clamped));

  let timerText = $derived(h === 0 ? `${minutes}:${seconds}` : `${hours}:${minutes}:${seconds}`);
  let title = $derived(`${hours}:${minutes}:${seconds}`);
</script>

{#if mode === 'timer'}
  <span class="circular-timer" {title}>
    <svg viewBox="0 0 100 100" class="ct-svg" aria-hidden="true">
      <circle cx="50" cy="50" r={R} stroke="var(--border)" stroke-width="4" fill="none" />
      <circle
        cx="50"
        cy="50"
        r={R}
        stroke="var(--xp)"
        stroke-width="4"
        fill="none"
        stroke-linecap="round"
        stroke-dasharray={CIRC}
        stroke-dashoffset={dashOffset}
        transform="rotate(-90 50 50)"
        style="transition: stroke-dashoffset 950ms linear;"
      />
    </svg>
    <span class="ct-text mono">{timerText}</span>
  </span>
{:else}
  <span class="analog-clock" style="--dial:{px}px" {title}>
    <svg viewBox="0 0 100 100" class="ac-svg" aria-hidden="true">
      <circle cx="50" cy="50" r="47" class="dial" />
      {#each Array.from({ length: 12 }, (_, i) => i) as i (i)}
        <line
          x1="50"
          y1="5"
          x2="50"
          y2={i % 3 === 0 ? 11 : 8}
          class="tick"
          class:major={i % 3 === 0}
          transform="rotate({i * 30} 50 50)"
        />
      {/each}
      <line
        x1="50"
        y1="54"
        x2="50"
        y2="30"
        class="hand hour-hand"
        transform="rotate({hourDeg} 50 50)"
      />
      <line
        x1="50"
        y1="54"
        x2="50"
        y2="18"
        class="hand min-hand"
        transform="rotate({minDeg} 50 50)"
      />
      <line
        x1="50"
        y1="56"
        x2="50"
        y2="12"
        class="hand sec-hand"
        transform="rotate({secDeg} 50 50)"
      />
      <circle cx="50" cy="50" r="2.2" class="hub" />
    </svg>
    {#if ampm}<span class="ac-ampm mono">{ampm}</span>{/if}
  </span>
{/if}

<style>
  .analog-clock {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: var(--dial);
    height: var(--dial);
  }
  .ac-svg {
    display: block;
    width: 100%;
    height: 100%;
  }
  .dial {
    fill: var(--elevated);
    stroke: var(--border);
    stroke-width: 1.5;
  }
  .tick {
    stroke: var(--text-muted);
    stroke-width: 1;
    stroke-linecap: round;
  }
  .tick.major {
    stroke: var(--text-secondary);
    stroke-width: 1.6;
  }
  .hand {
    stroke-linecap: round;
    transition: transform 200ms ease;
  }
  .hour-hand {
    stroke: var(--text-primary);
    stroke-width: 3.5;
  }
  .min-hand {
    stroke: var(--text-primary);
    stroke-width: 2.2;
  }
  .sec-hand {
    stroke: var(--xp);
    stroke-width: 1;
    transition: none;
  }
  .hub {
    fill: var(--xp);
  }
  .ac-ampm {
    position: absolute;
    bottom: 12%;
    font-size: 9px;
    color: var(--text-muted);
    letter-spacing: 0.08em;
  }

  .circular-timer {
    position: relative;
    display: block;
    width: 100%;
    height: 100%;
    container-type: size;
  }
  .ct-svg {
    display: block;
    width: 100%;
    height: 100%;
  }
  .ct-text {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-mono, monospace);
    font-weight: 300;
    color: var(--text-primary);
    letter-spacing: 0.04em;
    /* Scales with the dial container (150px ring → ~30px, 220px → ~44px). */
    font-size: 24px;
    font-size: 20cqmin;
    line-height: 1;
    white-space: nowrap;
  }
</style>
