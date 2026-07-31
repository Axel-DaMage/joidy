<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { ChevronRight } from 'lucide-svelte';
  import type { TreeNode } from '$lib/utils/fileTree';

  export let nodes: TreeNode[];
  export let collapsed: Set<string>;        // shared mutable set from parent
  export let selectedNoteId: number | null;
  export let depth = 0;

  const dispatch = createEventDispatcher<{ select: import('$lib/api').Note; toggle: string }>();

  function toggle(path: string) {
    if (collapsed.has(path)) collapsed.delete(path);
    else collapsed.add(path);
    dispatch('toggle', path); // bubble up to trigger Svelte reactivity
  }
</script>

{#each nodes as node (node.path)}
  {#if node.type === 'folder'}
    <!-- Folder row -->
    <div
      class="tree-row folder-row"
      style="padding-left: {8 + depth * 14}px"
      role="button"
      tabindex="0"
      aria-expanded={!collapsed.has(node.path)}
      onclick={() => toggle(node.path)}
      onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggle(node.path))}
    >
      <span class="chevron" class:open={!collapsed.has(node.path)}>
        <ChevronRight size={11} />
      </span>
      <span class="icon">{node.icon}</span>
      <span class="row-name folder-name">{node.name}</span>
      <span class="count">{node.children.length}</span>
    </div>

    {#if !collapsed.has(node.path)}
      <svelte:self
        nodes={node.children}
        {collapsed}
        {selectedNoteId}
        depth={depth + 1}
        on:select
        on:toggle
      />
    {/if}

  {:else}
    <!-- File row -->
    <div
      class="tree-row file-row"
      class:active={node.note?.id === selectedNoteId}
      style="padding-left: {20 + depth * 14}px"
      role="button"
      tabindex="0"
      aria-selected={node.note?.id === selectedNoteId}
      onclick={() => node.note && dispatch('select', node.note)}
      onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && node.note && (e.preventDefault(), dispatch('select', node.note))}
    >
      <span class="icon file-icon">{node.icon}</span>
      <span class="row-name file-name">{node.name}</span>
    </div>
  {/if}
{/each}

<style>
  .tree-row {
    display: flex;
    align-items: center;
    gap: 5px;
    padding-right: 8px;
    height: 26px;
    cursor: pointer;
    user-select: none;
    border-radius: 3px;
    margin: 0 4px;
    transition: background var(--t-fast);
    min-width: 0;
  }
  .tree-row:hover { background: var(--hover); }
  .file-row.active {
    background: var(--elevated);
    color: var(--text-primary);
  }

  .chevron {
    color: var(--text-muted);
    display: flex;
    align-items: center;
    flex-shrink: 0;
    transition: transform var(--t-fast);
  }
  .chevron.open { transform: rotate(90deg); }

  .icon {
    font-size: 13px;
    line-height: 1;
    flex-shrink: 0;
    width: 16px;
    text-align: center;
  }
  .file-icon { font-size: 11px; }

  .row-name {
    font-size: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
    min-width: 0;
  }
  .folder-name {
    color: var(--text-secondary);
    font-family: var(--font-sans);
  }
  .file-name {
    color: var(--text-secondary);
    font-family: var(--font-sans);
  }
  .file-row.active .file-name { color: var(--text-primary); }

  .count {
    font-size: 10px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    flex-shrink: 0;
  }
</style>
