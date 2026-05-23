<script lang="ts">
  import * as L from 'lucide-svelte';

  export let name: string = '';
  export let size: number = 18;
  export let color: string | undefined = undefined;

  const emojiRegex = /\p{Extended_Pictographic}/u;

  $: isEmoji = emojiRegex.test(name);
  $: comp = (L as Record<string, any>)[name] || L.Circle;
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
    this={comp}
    {size}
    {color}
    style="width: {size}px; height: {size}px; color: {color || 'inherit'}; display: inline-flex; flex-shrink: 0;"
  />
{/if}
