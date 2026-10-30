<script lang="ts">
  import type { Component } from 'svelte';
  import { clockStyle } from '$lib/stores/settings';
  import { DEFAULT_CLOCK_STYLE } from '$lib/utils/clock';
  import type { ClockStyleProps } from './types';
  import DigitalClock from './DigitalClock.svelte';

  /**
   * Renders the user's selected clock style (#707). Each style is a
   * self-contained component implementing `ClockStyleProps`, lazy-loaded via
   * dynamic import so unused styles stay out of the bundle chunk. Falls back
   * to the (statically bundled) Digital style if the selected style fails to
   * load. Every style lives inside the fixed `.clock-frame` box (#1093) and a
   * same-size skeleton covers the async chunk load (no layout flash).
   */
  async function loadStyle(style: string): Promise<Component<ClockStyleProps>> {
    switch (style) {
      case 'circular':
        return (await import('./CircularClock.svelte')).default;
      case 'material':
        return (await import('./MaterialClock.svelte')).default;
      case 'minimalist':
        return (await import('./MinimalistClock.svelte')).default;
      case 'flip':
        return (await import('./FlipClock.svelte')).default;
      case 'binary':
        return (await import('./BinaryClock.svelte')).default;
      default:
        return DigitalClock;
    }
  }

  let {
    mode = 'clock',
    size = 'md',
    hours,
    minutes,
    seconds,
    ampm = null,
    h = 0,
    m = 0,
    s = 0,
    progress = 1,
  }: ClockStyleProps = $props();

  let Active = $state<Component<ClockStyleProps>>(DigitalClock);
  let ready = $state(false);
  let loadToken = 0;

  $effect(() => {
    const style = $clockStyle ?? DEFAULT_CLOCK_STYLE;
    const token = ++loadToken;
    ready = false;
    loadStyle(style)
      .then((comp) => {
        if (token === loadToken) {
          Active = comp;
          ready = true;
        }
      })
      .catch(() => {
        if (token === loadToken) {
          Active = DigitalClock;
          ready = true;
        }
      });
  });
</script>

<span
  class="clock-frame s-{size}"
  class:mode-timer={mode === 'timer'}
  class:style-circular={($clockStyle ?? DEFAULT_CLOCK_STYLE) === 'circular'}
>
  {#if ready}
    <Active {mode} {size} {hours} {minutes} {seconds} {ampm} {h} {m} {s} {progress} />
  {:else}
    <span class="clock-skeleton" aria-hidden="true"></span>
  {/if}
</span>

<style>
  /*
   * Fixed display box (#1093) — metric documented in ./types.ts: every
   * style is hosted here so style/phase switches never move the surface.
   */
  .clock-frame {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: calc(8ch + 2em);
    min-height: 1.5em;
    font-family: var(--font-mono, monospace);
    font-variant-numeric: tabular-nums;
    line-height: 1;
    white-space: nowrap;
  }
  .clock-frame.s-sm {
    font-size: 0.85em;
  }
  .clock-frame.s-md {
    font-size: 1em;
  }
  .clock-frame.s-lg {
    font-size: 1.15em;
  }
  /* The circular style owns its dial: in timer mode the frame fills the
     ring-wrap instead of reserving text space. */
  .clock-frame.style-circular.mode-timer {
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
  }
  .clock-skeleton {
    width: calc(8ch + 0.5em);
    height: 1em;
    border-radius: 0.3em;
    background: var(--elevated);
    animation: skeleton-pulse 1.2s ease-in-out infinite;
  }
  @keyframes skeleton-pulse {
    0%,
    100% {
      opacity: 0.45;
    }
    50% {
      opacity: 0.75;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .clock-skeleton {
      animation: none;
    }
  }
</style>
