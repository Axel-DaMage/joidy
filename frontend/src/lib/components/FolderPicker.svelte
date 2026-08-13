<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { FlatNode } from '$lib/utils/fileTree';
  import { FolderRoot } from 'lucide-svelte';
  import DynamicIcon from './DynamicIcon.svelte';
  import { t } from 'svelte-i18n';

  export let flatNodes: FlatNode[] = [];

  const dispatch = createEventDispatcher<{
    close: void;
    select: string;
  }>();

  let selectedPath = '';
  let search = '';

  $: folders = flatNodes.filter(n => n.type === 'folder' && (!search || n.path.toLowerCase().includes(search.toLowerCase())));
</script>

<div class="folder-picker-backdrop" onclick={() => dispatch('close')} role="button" tabindex="-1" onkeydown={(e) => e.key === 'Enter' && dispatch('close')}>
  <div class="folder-picker" onclick={(e) => e.stopPropagation()} role="button" tabindex="-1" onkeydown={(e) => e.stopPropagation()}>
    <h3 class="folder-modal-title">{$t('folderPicker.title')}</h3>

    <input type="text" class="input mono" bind:value={search} placeholder={$t('folderPicker.searchPlaceholder')} style="width:100%; box-sizing:border-box; margin-bottom:8px;" />

    <div class="folder-list">
      <button
        class="folder-opt"
        class:selected={selectedPath === ''}
        onclick={() => selectedPath = ''}
      >
        <FolderRoot size={12} />
        (Raíz)
      </button>
      {#each folders as f}
        <button
          class="folder-opt"
          class:selected={selectedPath === f.path}
          onclick={() => selectedPath = f.path}
        >
          <span class="folder-opt-indent" style="width: {f.depth * 14}px"></span>
          <DynamicIcon name={f.icon || 'Folder'} size={12} color={f.color} />
          <span>{f.name}</span>
        </button>
      {/each}
      {#if folders.length === 0}
        <p class="muted">{$t('folderPicker.noResults')}</p>
      {/if}
    </div>

    <div class="folder-modal-btns">
      <button onclick={() => dispatch('close')}>{$t('folderPicker.cancel')}</button>
      <button class="primary" onclick={() => dispatch('select', selectedPath)}>{$t('folderPicker.moveHere')}</button>
    </div>
  </div>
</div>

<style>
  .folder-picker-backdrop {
    position: fixed; inset: 0; z-index: var(--z-overlay);
    background: rgba(0,0,0,0.3);
    display: flex; align-items: center; justify-content: center;
  }
  .folder-picker {
    background: var(--surface, #fff);
    border: 1px solid var(--border, #ddd);
    border-radius: var(--r, 8px);
    padding: 20px;
    min-width: 300px;
    max-width: 420px;
    max-height: 70vh;
    display: flex;
    flex-direction: column;
  }
  .folder-list {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-bottom: 12px;
    min-height: 100px;
  }
  .folder-opt {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: none;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    text-align: left;
    font-size: 0.85rem;
    color: var(--text-primary, #222);
    width: 100%;
  }
  .folder-opt:hover { background: var(--hover, #f0f0f0); }
  .folder-opt.selected { background: var(--elevated, #e8e8e8); }
  .folder-opt-indent { flex-shrink: 0; }
  .muted {
    color: var(--color-muted, #888);
    font-size: 0.8rem;
    text-align: center;
    padding: 24px 0;
  }
  .folder-modal-btns {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
  .folder-modal-title {
    margin: 0 0 12px;
    font-size: 1rem;
  }
  .input {
    padding: 6px 10px;
    border: 1px solid var(--border, #ddd);
    border-radius: 4px;
    background: var(--bg, #fff);
    color: var(--text-primary, #222);
    font-size: 0.85rem;
    outline: none;
  }
  .mono { font-family: var(--font-mono, monospace); }
  .primary {
    background: var(--accent, #4a90d9);
    color: var(--accent-contrast-text, #fff);
    border: 1px solid var(--accent, #4a90d9);
    padding: 6px 16px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
  }
  button:not(.primary) {
    padding: 6px 16px;
    border: 1px solid var(--border, #ddd);
    border-radius: 4px;
    background: var(--bg, #fff);
    cursor: pointer;
    font-size: 0.85rem;
    color: var(--text-primary, #222);
  }
</style>
