<script lang="ts">
  import type { ClockStyleProps } from './types';

  let {
    hours,
    minutes,
    seconds,
    ampm = null,
    h = 0,
    mode = 'clock',
    size = 'md',
  }: ClockStyleProps = $props();

  let text = $derived(
    mode === 'timer' && h === 0 ? `${minutes}:${seconds}` : `${hours}:${minutes}:${seconds}`
  );
</script>

<span class="material-clock s-{size}">
  <span class="mc-time">{text}</span>
  {#if ampm}<span class="mc-ampm">{ampm}</span>{/if}
</span>

<style>
  .material-clock {
    display: inline-flex;
    align-items: baseline;
    gap: 0.3em;
    padding: 0.4em 0.7em;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r, 8px);
    box-shadow:
      0 2px 4px rgba(0, 0, 0, 0.22),
      0 1px 2px rgba(0, 0, 0, 0.18);
    white-space: nowrap;
  }
  .mc-time {
    font-family: var(--font-sans, sans-serif);
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: 0.02em;
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }
  .mc-ampm {
    font-size: 0.5em;
    font-weight: 600;
    color: var(--xp);
    letter-spacing: 0.06em;
  }
  .s-sm {
    font-size: 0.85em;
  }
  .s-md {
    font-size: 1em;
  }
  .s-lg {
    font-size: 1.15em;
  }
</style>
