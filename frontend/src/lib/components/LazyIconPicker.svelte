<script lang="ts">
  import { onMount, type Component } from 'svelte';

  interface Props {
    selected?: string;
    color?: string;
    onSelect: (icon: string) => void;
  }

  let { selected = '', color, onSelect }: Props = $props();

  let IconPicker = $state<Component | null>(null);

  onMount(async () => {
    const mod = await import('./IconPicker.svelte');
    IconPicker = mod.default;
  });
</script>

{#if IconPicker}
  <svelte:component this={IconPicker} {selected} {color} {onSelect} />
{/if}
