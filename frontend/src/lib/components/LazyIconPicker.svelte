<script lang="ts">
  import { onMount } from 'svelte';
  import { logger } from '$lib/utils/logger';
  import { t } from 'svelte-i18n';

  interface Props {
    selected?: string;
    color?: string;
    onSelect: (icon: string) => void;
  }

  let { selected = '', color, onSelect }: Props = $props();

  let IconPicker = $state<any>(null);
  // #1459 — a failed chunk rendered nothing forever; offer a retry.
  let loadError = $state(false);

  function loadPicker() {
    loadError = false;
    import('./IconPicker.svelte')
      .then((mod) => (IconPicker = mod.default))
      .catch((err) => {
        logger.error('[LazyIconPicker] IconPicker chunk failed:', err);
        loadError = true;
      });
  }

  onMount(loadPicker);
</script>

{#if IconPicker}
  <IconPicker {selected} {color} {onSelect} />
{:else if loadError}
  <button type="button" class="lazy-icon-picker-error" onclick={loadPicker}>
    {$t('common.retry')}
  </button>
{/if}

<style>
  .lazy-icon-picker-error {
    width: 100%;
    padding: 8px;
    font-size: 11px;
    color: var(--text-muted);
    background: transparent;
    border: 1px dashed var(--border);
    border-radius: var(--r-sm, 4px);
    cursor: pointer;
  }
  .lazy-icon-picker-error:hover {
    color: var(--text-primary);
    border-color: var(--text-muted);
  }
</style>
