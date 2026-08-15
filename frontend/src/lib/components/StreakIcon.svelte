<script lang="ts">
  import { Circle } from 'lucide-svelte';
  import { loadLucideIcon } from '$lib/utils/lucideIcons';

  export let name: string = '';
  export let size: number = 18;
  export let color: string | undefined = undefined;

  const emojiRegex = /\p{Extended_Pictographic}/u;

  $: isEmoji = emojiRegex.test(name);

  // Lucide icons are loaded on demand via dynamic import so the whole icon
  // library is no longer bundled into the main chunk (#209). A `Circle`
  // placeholder is shown until the requested icon chunk resolves.
  let lucideComp: any = Circle;
  let _req = 0;

  $: {
    const req = ++_req;
    if (!name) {
      lucideComp = Circle;
    } else {
      loadLucideIcon(name).then((loaded) => {
        // Guard against stale loads when `name` changes quickly.
        if (req === _req) lucideComp = loaded ?? Circle;
      });
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
