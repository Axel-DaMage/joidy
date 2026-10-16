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

  let groups = $derived(
    mode === 'timer' && h === 0 ? [minutes, seconds] : [hours, minutes, seconds]
  );
</script>

<span class="flip-clock s-{size}">
  {#each groups as group, gi (gi)}
    {#if gi > 0}<span class="flip-sep">:</span>{/if}
    {#each group.split('') as digit, di (`${gi}:${di}`)}
      <span class="flip-cell">
        {#key digit}
          <span class="flip-card">{digit}</span>
        {/key}
      </span>
    {/each}
  {/each}
  {#if ampm}<span class="flip-ampm">{ampm}</span>{/if}
</span>

<style>
  .flip-clock {
    display: inline-flex;
    align-items: center;
    gap: 0.08em;
    white-space: nowrap;
  }
  .flip-cell {
    display: inline-flex;
    perspective: 8em;
  }
  .flip-card {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 0.72em;
    padding: 0.12em 0.08em;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: 0.14em;
    font-family: var(--font-mono, monospace);
    font-weight: 500;
    color: var(--text-primary);
    line-height: 1;
    box-shadow: 0 0.06em 0 rgba(0, 0, 0, 0.25);
    animation: flip-in 280ms ease-out;
    transform-origin: center 55%;
    backface-visibility: hidden;
  }
  .flip-sep {
    color: var(--text-muted);
    font-family: var(--font-mono, monospace);
    margin: 0 0.06em;
  }
  .flip-ampm {
    font-size: 0.45em;
    margin-left: 0.4em;
    color: var(--text-muted);
    font-family: var(--font-mono, monospace);
    letter-spacing: 0.05em;
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

  @keyframes flip-in {
    from {
      transform: rotateX(-88deg);
      opacity: 0.35;
    }
    to {
      transform: rotateX(0deg);
      opacity: 1;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .flip-card {
      animation: none;
    }
  }
</style>
