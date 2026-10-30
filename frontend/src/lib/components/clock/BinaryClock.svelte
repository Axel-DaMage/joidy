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

  // One column of 4 bits per decimal digit (true binary-coded-decimal clock).
  let layout = $derived(clockSegments({ hours, minutes, seconds, h }, mode));
  let ghostHours = $derived(layout.ghostLead > 0);

  function bitsOf(ch: string): boolean[] {
    const v = parseInt(ch, 10);
    if (Number.isNaN(v)) return [false, false, false, false];
    return [Boolean(v & 8), Boolean(v & 4), Boolean(v & 2), Boolean(v & 1)];
  }
</script>

<span class="binary-clock" title="{hours}:{minutes}:{seconds}">
  {#each layout.groups as group, gi (gi)}
    {#if gi > 0}
      <span class="b-sep" class:seg-ghost={ghostHours && gi === 1} aria-hidden="true"></span>
    {/if}
    {#each group.split('') as ch, ci (`${gi}:${ci}`)}
      <span class="b-col" class:seg-ghost={ghostHours && gi === 0}>
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
  }
  .b-col {
    display: inline-flex;
    flex-direction: column;
    gap: 0.18em;
  }
  .b-col.seg-ghost,
  .b-sep.seg-ghost {
    visibility: hidden;
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
</style>
