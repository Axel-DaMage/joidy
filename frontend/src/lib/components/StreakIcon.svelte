<script lang="ts">
  import { Circle } from 'lucide-svelte';
  import { getLucideIcon } from '$lib/utils/lucideIcons';

  export let name: string = '';
  export let size: number = 18;
  export let color: string | undefined = undefined;

  const emojiRegex = /\p{Extended_Pictographic}/u;

  $: isEmoji = emojiRegex.test(name);

  // Lucide icons are resolved synchronously from the bundled namespace
  // import — no async placeholder flicker (#693). Falls back to `Circle`
  // for unknown names.
  let lucideComp: any = Circle;
  $: {
    if (!name) {
      lucideComp = Circle;
    } else {
      lucideComp = getLucideIcon(name) ?? Circle;
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
