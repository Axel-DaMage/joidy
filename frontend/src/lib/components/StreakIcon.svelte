<script lang="ts">
  import * as L from 'lucide-svelte';

  export let name: string = '';
  export let size: number = 18;
  export let color: string | undefined = undefined;

  $: comp = (L as Record<string, any>)[name] || L.Circle;
</script>

<svelte:component
  this={comp}
  {size}
  {color}
  style="width: {size}px; height: {size}px; color: {color || 'inherit'}; display: inline-flex; flex-shrink: 0;"
/>
