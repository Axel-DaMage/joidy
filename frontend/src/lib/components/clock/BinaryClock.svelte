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

  // One column of 4 bits per decimal digit (true binary-coded-decimal clock).
  let groups = $derived(
    mode === 'timer' && h === 0 ? [minutes, seconds] : [hours, minutes, seconds]
  );

  function bitsOf(ch: string): boolean[] {
    const v = parseInt(ch, 10);
    if (Number.isNaN(v)) return [false, false, false, false];
    return [Boolean(v & 8), Boolean(v & 4), Boolean(v & 2), Boolean(v & 1)];
  }
</script>

<span class="binary-clock s-{size}" title="{hours}:{minutes}:{seconds}">
  {#each groups as group, gi (gi)}
    {#if gi > 0}<span class="b-sep" aria-hidden="true"></span>{/if}
    {#each group.split('') as ch, ci (`${gi}:${ci}`)}
      <span class="b-col">
        {#each bitsOf(ch) as bit, bi (bi)}
          <span class="b-dot" class:lit={bit}></span>
        {/each}
      </span>
    {/each}
  {/each}
  {#if ampm}<span class="b-ampm mono">{ampm}</span>{/if}
</span>

<style>
  .binary-clock {
    display: inline-flex;
    align-items: center;
    gap: 0.22em;
    padding: 0.25em 0.35em;
  }
  .b-col {
    display: inline-flex;
    flex-direction: column;
    gap: 0.18em;
  }
  .b-dot {
    width: 0.22em;
    height: 0.22em;
    border-radius: 50%;
    background: var(--border);
    transition: background var(--t-fast, 120ms ease);
  }
  .b-dot.lit {
    background: var(--xp);
    box-shadow: 0 0 0.12em color-mix(in srgb, var(--xp) 60%, transparent);
  }
  .b-sep {
    width: 0.28em;
  }
  .b-ampm {
    font-size: 0.4em;
    color: var(--text-muted);
    margin-left: 0.3em;
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
