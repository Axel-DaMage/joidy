<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { displayTagName } from '$lib/utils/format';
  import { t } from 'svelte-i18n';
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
  onclick={handleClick}
  onkeydown={handleKeydown}
  role="button"
  tabindex="0"
>
  {displayTagName(tag)}
  {#if isAI}
    <span class="ai-badge" title={$t('tagChip.aiSuggestion')}>ia</span>
  {/if}
  {#if removable}
    <button onclick={handleRemove} aria-label={$t('tagChip.removeTag', { values: { name: displayTagName(tag) } })}>×</button>
  {/if}
</span>

<style>
  .ai-badge {
    font-size: 9px;
    opacity: 0.7;
    letter-spacing: 0.05em;
  }
</style>
