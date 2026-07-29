<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  export let tag: string;
  export let removable = false;
  export let isAI = false;
  export let onremove: ((tag: string) => void) | undefined = undefined;
  export let onclick: ((tag: string) => void) | undefined = undefined;

  const dispatch = createEventDispatcher<{ remove: string; click: string }>();

  function handleClick(e: MouseEvent) {
    e.stopPropagation();
    dispatch('click', tag);
    if (onclick) onclick(tag);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault();
      e.stopPropagation();
      dispatch('click', tag);
      if (onclick) onclick(tag);
    }
  }

  function handleRemove(e: MouseEvent) {
    e.stopPropagation();
    dispatch('remove', tag);
    if (onremove) onremove(tag);
  }
</script>

<span 
  class="tag-chip" 
  class:ai={isAI} 
  on:click={handleClick}
  on:keydown={handleKeydown}
  role="button"
  tabindex="0"
>
  {tag}
  {#if isAI}
    <span class="ai-badge" title="Sugerencia de IA">ia</span>
  {/if}
  {#if removable}
    <button on:click={handleRemove} aria-label="Eliminar etiqueta {tag}">×</button>
  {/if}
</span>

<style>
  .ai-badge {
    font-size: 9px;
    opacity: 0.7;
    letter-spacing: 0.05em;
  }
</style>
