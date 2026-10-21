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
   * load.
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
  let loadToken = 0;

  $effect(() => {
    const style = $clockStyle ?? DEFAULT_CLOCK_STYLE;
    const token = ++loadToken;
    loadStyle(style)
      .then((comp) => {
        if (token === loadToken) Active = comp;
      })
      .catch(() => {
        if (token === loadToken) Active = DigitalClock;
      });
  });
</script>

<Active {mode} {size} {hours} {minutes} {seconds} {ampm} {h} {m} {s} {progress} />
