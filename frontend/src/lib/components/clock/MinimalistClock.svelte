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

  // Spec: minimalist clock shows HH:MM (no seconds, no decoration).
  let text = $derived(
    mode === 'clock'
      ? `${hours}:${minutes}`
      : h === 0
        ? `${minutes}:${seconds}`
        : `${hours}:${minutes}:${seconds}`
  );
</script>

<span class="minimal-clock s-{size}">
  {text}{#if ampm}<span class="ampm">{ampm}</span>{/if}
</span>

<style>
  .minimal-clock {
    font-family: var(--font-sans, sans-serif);
    font-weight: 200;
    color: var(--text-primary);
    letter-spacing: 0.12em;
    line-height: 1;
    white-space: nowrap;
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
  .ampm {
    font-size: 0.45em;
    margin-left: 0.35em;
    color: var(--text-muted);
  }
</style>
