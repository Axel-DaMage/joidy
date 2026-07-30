<script lang="ts">
  import { onMount } from 'svelte';

  interface Props {
    selected?: string;
    color?: string;
    onSelect: (icon: string) => void;
  }

  let { selected = '', color, onSelect }: Props = $props();

  let IconPicker = $state<any>(null);

  onMount(async () => {
    const mod = await import('./IconPicker.svelte');
    IconPicker = mod.default;
  });
</script>

{#if IconPicker}
  <IconPicker {selected} {color} {onSelect} />
{/if}
