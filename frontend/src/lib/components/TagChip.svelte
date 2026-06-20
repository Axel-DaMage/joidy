<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  export let tag: string;
  export let removable = false;
  export let isAI = false;

  const dispatch = createEventDispatcher<{ remove: string; click: string }>();
</script>

<span 
  class="tag-chip" 
  class:ai={isAI} 
  on:click|stopPropagation={() => dispatch('click', tag)}
  role="button"
  tabindex="0"
>
  {tag}
  {#if isAI}
    <span class="ai-badge" title="Sugerencia de IA">ia</span>
  {/if}
  {#if removable}
    <button on:click|stopPropagation={() => dispatch('remove', tag)} aria-label="Eliminar etiqueta {tag}">×</button>
  {/if}
</span>

<style>
  .ai-badge {
    font-size: 9px;
    opacity: 0.7;
    letter-spacing: 0.05em;
  }
</style>
