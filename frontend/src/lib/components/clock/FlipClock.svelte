<script lang="ts">
  import type { ClockStyleProps } from './types';
  import { clockSegments } from './segments';

  let {
    hours,
    minutes,
    seconds,
    ampm = null,
    h = 0,
    mode = 'clock',
  }: ClockStyleProps = $props();

  let layout = $derived(clockSegments({ hours, minutes, seconds, h }, mode));
  let ghostHours = $derived(layout.ghostLead > 0);
</script>

<span class="flip-clock">
  {#each layout.groups as group, gi (gi)}
    {#if gi > 0}
      <span class="flip-sep" class:seg-ghost={ghostHours && gi === 1}>:</span>
    {/if}
    {#each group.split('') as digit, di (`${gi}:${di}`)}
      <span class="flip-cell" class:seg-ghost={ghostHours && gi === 0}>
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
    gap: 0.04em;
    white-space: nowrap;
  }
  .flip-cell {
    display: inline-flex;
    perspective: 8em;
  }
  .flip-cell.seg-ghost,
  .flip-sep.seg-ghost {
    visibility: hidden;
  }
  .flip-card {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1ch;
    padding: 0.12em 0.08em;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: 0.14em;
    font-weight: 500;
    color: var(--text-primary);
    box-shadow: 0 0.06em 0 rgba(0, 0, 0, 0.25);
    animation: flip-in 280ms ease-out;
    transform-origin: center 55%;
    backface-visibility: hidden;
  }
  .flip-sep {
    color: var(--text-muted);
    margin: 0 0.06em;
  }
  .flip-ampm {
    font-size: 0.45em;
    margin-left: 0.4em;
    color: var(--text-muted);
    letter-spacing: 0.05em;
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
