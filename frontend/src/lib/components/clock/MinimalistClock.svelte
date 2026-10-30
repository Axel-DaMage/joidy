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

<span class="minimal-clock">
  {#if mode === 'clock'}
    <!-- Spec: minimalist clock shows HH:MM (no seconds, no decoration). -->
    {hours}:{minutes}
  {:else}
    {#if text.ghost}<span class="seg-ghost" aria-hidden="true">{text.ghost}</span>{/if}{text.body}
  {/if}
  {#if ampm}<span class="ampm">{ampm}</span>{/if}
</span>

<style>
  .minimal-clock {
    font-weight: 200;
    color: var(--text-primary);
    letter-spacing: 0.04em;
    white-space: nowrap;
  }
  .seg-ghost {
    visibility: hidden;
  }
  .ampm {
    font-size: 0.45em;
    margin-left: 0.35em;
    color: var(--text-muted);
  }
</style>
