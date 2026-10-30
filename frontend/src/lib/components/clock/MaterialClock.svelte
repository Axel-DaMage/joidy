<script lang="ts">
  import type { ClockStyleProps } from './types';
  import { clockSegments, segmentText } from './segments';

  let {
    hours,
    minutes,
    seconds,
    ampm = null,
    h = 0,
    mode = 'clock',
  }: ClockStyleProps = $props();

  let text = $derived(segmentText(clockSegments({ hours, minutes, seconds, h }, mode)));
</script>

<span class="material-clock">
  <span class="mc-time">
    {#if text.ghost}<span class="seg-ghost" aria-hidden="true">{text.ghost}</span>{/if}{text.body}
  </span>
  {#if ampm}<span class="mc-ampm">{ampm}</span>{/if}
</span>

<style>
  .material-clock {
    display: inline-flex;
    align-items: baseline;
    gap: 0.3em;
    padding: 0.2em 0.4em;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: 0.2em;
    box-shadow:
      0 2px 4px rgba(0, 0, 0, 0.22),
      0 1px 2px rgba(0, 0, 0, 0.18);
    white-space: nowrap;
  }
  .mc-time {
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: 0.04em;
    white-space: nowrap;
  }
  .seg-ghost {
    visibility: hidden;
  }
  .mc-ampm {
    font-size: 0.5em;
    font-weight: 600;
    color: var(--xp);
    letter-spacing: 0.06em;
  }
</style>
