<script lang="ts">
  import { Circle } from 'lucide-svelte';
  import * as LucideIcons from 'lucide-svelte';

  export let name: string = '';
  export let size: number = 18;
  export let color: string | undefined = undefined;

  const emojiRegex = /\p{Extended_Pictographic}/u;

  $: isEmoji = emojiRegex.test(name);

  // Convert kebab-case to PascalCase (e.g. "book-open" → "BookOpen")
  function toPascalCase(s: string): string {
    return s.split('-').map(p => p.charAt(0).toUpperCase() + p.slice(1)).join('');
  }

  // Synchronous lookup — handles both PascalCase and kebab-case names
  $: lucideComp = name ? ((LucideIcons as any)[name] || (LucideIcons as any)[toPascalCase(name)] || Circle) : Circle;
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
    style="width: {size}px; height: {size}px; color: {color || 'inherit'}; display: inline-flex; flex-shrink: 0;"
  />
{/if}
