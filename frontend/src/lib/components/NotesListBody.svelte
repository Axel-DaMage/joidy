<script lang="ts">
  import { tick } from 'svelte';
  import { ChevronRight, FilePen, Settings } from 'lucide-svelte';
  import DynamicIcon from './DynamicIcon.svelte';
  import NoteCard from './NoteCard.svelte';
  import VirtualList from './VirtualList.svelte';
  import {
    notes,
    notesLoading,
    loadingMore,
    hasMoreNotes,
    selectedNoteIds,
    bulkMode,
    toggleNoteSelection,
  } from '$lib/stores/notes';
  import {
    search,
    selectedNote,
    viewMode,
    sortMode,
    allCollapsed,
    collapsed,
    notesPrefsReady,
    scrollReady,
    filtered,
    flatNodes,
    listScrollEl,
    virtualScrollTop,
    __treeScrollTop,
    __listScrollTop,
  } from '$lib/stores/notesUi';
  import {
    openNote,
    openFolderCustomizer,
    handleContextMenu,
    toggleFolder,
    onListScroll,
    onVirtualScrollChange,
    handleNearBottom,
    persist,
    getNoteVisual,
  } from '$lib/utils/notesPage';
  import { t } from 'svelte-i18n';

  let lastRestoredViewMode: 'tree' | 'list' = 'tree';
  let scrollRestored = false;

  $: collapsedSignature = Array.from($collapsed).sort().join('|');

  // Persist prefs whenever these change (mirrors the original page reactive block).
  $: if ($notesPrefsReady) {
    $viewMode;
    $sortMode;
    $allCollapsed;
    collapsedSignature;
    $search;
    $selectedNote?.id;
    persist();
  }

  // Restore scroll position when the view mode flips away from the restored one.
  $: if ($notesPrefsReady && $viewMode !== lastRestoredViewMode) {
    lastRestoredViewMode = $viewMode;
    const target = $viewMode === 'tree' ? $__treeScrollTop : $__listScrollTop;
    $virtualScrollTop = target;
    tick().then(() => {
      const el = $listScrollEl;
      if (!el) return;
      el.scrollTop = target;
      $virtualScrollTop = target;
    });
  }

  // Apply the restored scroll position once prefs are loaded (the page sets
  // notesPrefsReady after reading localStorage).
  $: if ($notesPrefsReady && !scrollRestored) {
    scrollRestored = true;
    lastRestoredViewMode = $viewMode;
    tick().then(() => {
      const target = $viewMode === 'tree' ? $__treeScrollTop : $__listScrollTop;
      const el = $listScrollEl;
      if ($flatNodes.length > 50 || $filtered.length > 50) {
        $virtualScrollTop = target;
      } else if (el) {
        el.scrollTop = target;
      }
      $scrollReady = true;
    });
  }
</script>

<div
  class="list-scroll"
  class:scroll-ready={$scrollReady}
  bind:this={$listScrollEl}
  onscroll={onListScroll}
>
  {#if $notesLoading}
    <div class="empty-msg">{$t('notesPage.loading')}</div>
  {:else if $viewMode === 'tree'}
    {#if $flatNodes.length === 0}
      <div class="empty-msg">{$search ? 'Sin resultados.' : 'Sin notas.'}</div>
    {:else if $flatNodes.length > 50}
      <VirtualList
        items={$flatNodes}
        itemHeight={26}
        getKey={(n, i) => n.path ?? i}
        bind:scrollTop={$virtualScrollTop}
        onScrollChange={onVirtualScrollChange}
        let:item
        let:index
      >
        {#if item.type === 'folder'}
          <div
            class="tree-row folder-row"
            style="padding-left: {8 + item.depth * 14}px"
            role="button"
            tabindex="0"
            aria-expanded={!$collapsed.has(item.path)}
            onclick={() => toggleFolder(item.path)}
            onkeydown={(e) =>
              (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggleFolder(item.path))}
            oncontextmenu={(e) => handleContextMenu(e, item)}
          >
            <span class="chevron" class:open={!$collapsed.has(item.path)}>
              <ChevronRight size={11} />
            </span>
            <div class="t-icon">
              <DynamicIcon name={item.icon} size={13} color={item.color} pack={item.pack} />
            </div>
            <span class="t-name folder-name">{item.name}</span>
            <button
              class="folder-settings-btn"
              title={$t('notesPage.customizeFolder')}
              aria-label={$t('notesPage.customizeFolder')}
              onclick={(e) => {
                e.stopPropagation();
                openFolderCustomizer(item);
              }}
            >
              <Settings size={10} />
            </button>
            <span class="t-count">{item.childCount}</span>
          </div>
        {:else}
          <div
            class="tree-row file-row"
            class:active={item.note?.id === $selectedNote?.id}
            style="padding-left: {20 + item.depth * 14}px"
            role="button"
            tabindex="0"
            aria-pressed={item.note?.id === $selectedNote?.id}
            onclick={() => item.note && openNote(item.note)}
            onkeydown={(e) =>
              (e.key === 'Enter' || e.key === ' ') &&
              item.note &&
              (e.preventDefault(), openNote(item.note))}
            oncontextmenu={(e) => handleContextMenu(e, item)}
          >
            <div class="t-icon file-icon">
              <DynamicIcon name={item.icon} size={11} color={item.color} pack={item.pack} />
            </div>
            <span class="t-name file-name">{item.name}</span>
            <button
              class="folder-settings-btn"
              title={$t('notesPage.customizeNote')}
              aria-label={$t('notesPage.customizeNote')}
              onclick={(e) => {
                e.stopPropagation();
                openFolderCustomizer({
                  path: item.note?.source_path || item.path,
                  icon: item.icon,
                  color: item.color,
                  note: item.note,
                });
              }}
            >
              <Settings size={10} />
            </button>
          </div>
        {/if}
      </VirtualList>
    {:else}
      <div class="tree-wrap">
        {#each $flatNodes as node (node.path)}
          {#if node.type === 'folder'}
            <div
              class="tree-row folder-row"
              style="padding-left: {8 + node.depth * 14}px"
              role="button"
              tabindex="0"
              aria-expanded={!$collapsed.has(node.path)}
              onclick={() => toggleFolder(node.path)}
              onkeydown={(e) =>
                (e.key === 'Enter' || e.key === ' ') &&
                (e.preventDefault(), toggleFolder(node.path))}
              oncontextmenu={(e) => handleContextMenu(e, node)}
            >
              <span class="chevron" class:open={!$collapsed.has(node.path)}>
                <ChevronRight size={11} />
              </span>
              <div class="t-icon">
                <DynamicIcon name={node.icon} size={13} color={node.color} pack={node.pack} />
              </div>
              <span class="t-name folder-name">{node.name}</span>
              <button
                class="folder-settings-btn"
                title={$t('notesPage.customizeFolder')}
                aria-label={$t('notesPage.customizeFolder')}
                onclick={(e) => {
                  e.stopPropagation();
                  openFolderCustomizer(node);
                }}
              >
                <Settings size={10} />
              </button>
              <span class="t-count">{node.childCount}</span>
            </div>
          {:else}
            <div
              class="tree-row file-row"
              class:active={node.note?.id === $selectedNote?.id}
              style="padding-left: {20 + node.depth * 14}px"
              role="button"
              tabindex="0"
              aria-pressed={node.note?.id === $selectedNote?.id}
              onclick={() => node.note && openNote(node.note)}
              onkeydown={(e) =>
                (e.key === 'Enter' || e.key === ' ') &&
                node.note &&
                (e.preventDefault(), openNote(node.note))}
              oncontextmenu={(e) => handleContextMenu(e, node)}
            >
              <div class="t-icon file-icon">
                <DynamicIcon name={node.icon} size={11} color={node.color} pack={node.pack} />
              </div>
              <span class="t-name file-name">{node.name}</span>
              <button
                class="folder-settings-btn"
                title={$t('notesPage.customizeNote')}
                aria-label={$t('notesPage.customizeNote')}
                onclick={(e) => {
                  e.stopPropagation();
                  openFolderCustomizer({
                    path: node.note?.source_path || node.path,
                    icon: node.icon,
                    color: node.color,
                    note: node.note,
                  });
                }}
              >
                <Settings size={10} />
              </button>
            </div>
          {/if}
        {/each}
      </div>
    {/if}
  {:else}
    {#if $filtered.length === 0}
      <div class="empty-msg">{$search ? 'Sin resultados.' : 'Sin notas.'}</div>
    {:else if $filtered.length > 50}
      <VirtualList
        items={$filtered}
        itemHeight={52}
        bind:scrollTop={$virtualScrollTop}
        onScrollChange={onVirtualScrollChange}
        onNearBottom={handleNearBottom}
        let:item
        let:index
      >
        <NoteCard
          note={item}
          active={$selectedNote?.id === item.id}
          selected={$selectedNoteIds.has(item.id)}
          bulkMode={$bulkMode}
          on:select={(e) => openNote(e.detail)}
          on:toggleSelect={(e) => toggleNoteSelection(e.detail)}
          on:customize={(e) => openFolderCustomizer(e.detail)}
        />
      </VirtualList>
    {:else}
      {#each $filtered as note}
        <NoteCard
          {note}
          active={$selectedNote?.id === note.id}
          selected={$selectedNoteIds.has(note.id)}
          bulkMode={$bulkMode}
          on:select={(e) => openNote(e.detail)}
          on:toggleSelect={(e) => toggleNoteSelection(e.detail)}
          on:customize={(e) => openFolderCustomizer(e.detail)}
        />
      {/each}
    {/if}
  {/if}

  {#if $loadingMore}
    <div class="loading-more-indicator">{$t('notesPage.loading')}</div>
  {/if}
</div>

<style>
  /* ── Panel ── */
  .notes-list {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    min-width: 0;
  }

  .list-scroll {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
  }
  .list-scroll:not(.scroll-ready) {
    visibility: hidden;
  }

  .tree-wrap {
    padding: 4px 0;
  }

  .empty-msg {
    padding: 32px 16px;
    text-align: center;
    color: var(--text-muted);
    font-size: 12px;
  }

  .loading-more-indicator {
    text-align: center;
    padding: 10px 12px;
    font-size: 12px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  /* ── Tree rows ── */
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
  .tree-row:hover {
    background: var(--hover);
  }
  .file-row.active {
    background: var(--elevated);
  }

  .chevron {
    color: var(--text-muted);
    display: flex;
    align-items: center;
    flex-shrink: 0;
    transition: transform var(--t-fast);
  }
  .chevron.open {
    transform: rotate(90deg);
  }

  .t-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 16px;
    height: 16px;
  }
  .file-icon {
    opacity: 0.9;
  }

  .t-name {
    font-size: 12px;
    font-family: var(--font-sans);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
    min-width: 0;
    color: var(--text-secondary);
  }
  .file-row.active .t-name {
    color: var(--text-primary);
  }

  .t-count {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    flex-shrink: 0;
  }

  /* Folder settings button */
  .folder-settings-btn {
    display: none;
    padding: 2px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    border-radius: 3px;
    margin-left: 4px;
  }
  .folder-row:hover .folder-settings-btn,
  .file-row:hover .folder-settings-btn {
    display: flex;
  }
  .folder-settings-btn:hover {
    color: var(--accent);
    background: var(--border-light);
  }

  /* ── Responsive ── */
</style>
