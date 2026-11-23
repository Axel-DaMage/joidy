<script lang="ts">
  import Circle from 'lucide-svelte/icons/circle';
  import { getLucideIcon, loadLucideIcon } from '$lib/utils/lucideIcons';
  import { logger } from '$lib/utils/logger';

  export let name: string = '';
  export let size: number = 18;
  export let color: string | undefined = undefined;

  const emojiRegex = /\p{Extended_Pictographic}/u;

  $: isEmoji = emojiRegex.test(name);

  // Lucide icons resolve synchronously from the curated map (#1311). Names
  // outside it load the full set as a single lazy chunk — `Circle` shows
  // until it lands.
  let lucideComp: any = Circle;
  $: {
    let resolved: any = Circle;
    if (name) {
      resolved = getLucideIcon(name) ?? Circle;
    }
    lucideComp = resolved;
    // NB: test the local `resolved`, never `lucideComp` — reading the state
    // var inside its own reactive block makes it a self-dependency, and since
    // components are objects every assignment re-triggers the block →
    // infinite render loop.
    if (name && !isEmoji && resolved === Circle) {
      const requested = name;
      loadLucideIcon(requested)
        .then((loaded) => {
          if (loaded && name === requested) lucideComp = loaded;
        })
        // Failed lazy chunk: keep the Circle fallback (#1459).
        .catch((err) => logger.warn('[StreakIcon] lazy icon load failed:', err));
    }
  }
</script>

{#if isEmoji}
  <span
    style="width: {size}px; height: {size}px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: {size}px; line-height: 1;"
    aria-hidden="true"
  >
    {name}
  </span>
{:else}
  <svelte:component
    this={lucideComp}
    {size}
    {color}
    style="width: {size}px; height: {size}px; color: {color ||
      'inherit'}; display: inline-flex; flex-shrink: 0;"
  />
{/if}
