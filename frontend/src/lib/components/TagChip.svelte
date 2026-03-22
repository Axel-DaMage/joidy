<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  export let tag: string;
  export let removable = false;
  export let isAI = false;

  const dispatch = createEventDispatcher<{ remove: string }>();
</script>

<span class="tag-chip" class:ai={isAI}>
  {tag}
  {#if isAI}
    <span class="ai-badge">ai</span>
  {/if}
  {#if removable}
    <button on:click={() => dispatch('remove', tag)} aria-label="Remove tag {tag}">×</button>
  {/if}
</span>

<style>
  .ai-badge {
    font-size: 9px;
    opacity: 0.7;
    letter-spacing: 0.05em;
  }
</style>
