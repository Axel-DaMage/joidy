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

<span class="digital-clock s-{size}">
  {text}{#if ampm}<span class="ampm">{ampm}</span>{/if}
</span>

<style>
  .digital-clock {
    font-family: var(--font-mono, monospace);
    font-weight: 300;
    color: var(--text-primary);
    letter-spacing: 0.08em;
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
    letter-spacing: 0.05em;
  }
</style>
