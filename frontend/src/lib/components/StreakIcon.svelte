<script lang="ts">
  import Circle from 'lucide-svelte/icons/circle';
  import { getLucideIcon, loadLucideIcon } from '$lib/utils/lucideIcons';

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
    if (!name) {
      lucideComp = Circle;
    } else {
      lucideComp = getLucideIcon(name) ?? Circle;
      if (!isEmoji && lucideComp === Circle) {
        const requested = name;
        loadLucideIcon(requested).then((loaded) => {
          if (loaded && name === requested) lucideComp = loaded;
        });
      }
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
