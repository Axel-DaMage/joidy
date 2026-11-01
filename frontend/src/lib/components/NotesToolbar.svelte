<script lang="ts">
  import {
    Search,
    Plus,
    X,
    List,
    FolderTree,
    FolderPlus,
    ChevronsUpDown,
    ArrowUpDown,
    Settings,
    SquareCheckBig,
    FilePen,
  } from 'lucide-svelte';
  import DynamicIcon from './DynamicIcon.svelte';
  import {
    notes,
    selectedNoteIds,
    bulkMode,
    selectAllNotes,
    clearNoteSelection,
    deleteSelectedNotes,
    tagSelectedNotes,
    untagSelectedNotes,
  } from '$lib/stores/notes';
  import {
    search,
    viewMode,
    sortMode,
    allCollapsed,
    filtered,
    totalNotes,
    deleteModalOpen,
    deleteMode,
    notesPrefsReady,
  } from '$lib/stores/notesUi';
  import {
    openNew,
    setSortMode,
    toggleCollapseAll,
    handleCreateFolder,
    persist,
    handleDelete,
  } from '$lib/utils/notesPage';
  import type { SortMode } from '$lib/utils/fileTree';
  import { t } from 'svelte-i18n';

  let showSortMenu = false;

  function onSetSort(mode: SortMode) {
    setSortMode(mode);
    showSortMenu = false;
  }
</script>

<svelte:window
  onclick={() => {
    showSortMenu = false;
  }}
/>

<div class="tree-actions-bar">
  <div class="actions-left">
    <button
      class="icon-btn"
      title={$t('notesPage.createNote')}
      aria-label={$t('notesPage.createNote')}
      onclick={() => openNew()}><FilePen size={13} /></button
    >
    <button
      class="icon-btn"
      title={$t('notesPage.createFolder')}
      aria-label={$t('notesPage.createFolder')}
      onclick={handleCreateFolder}><FolderPlus size={13} /></button
    >
    <div class="sort-wrapper">
      <button
        class="icon-btn"
        title={$t('notesPage.changeOrder')}
        aria-label={$t('notesPage.changeOrder')}
        onclick={(e) => {
          e.stopPropagation();
          showSortMenu = !showSortMenu;
        }}
      >
        <ArrowUpDown size={13} />
      </button>
      {#if showSortMenu}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="sort-menu" onclick={(e) => e.stopPropagation()}>
          <button class="sort-btn" class:active={$sortMode === 'az'} onclick={() => onSetSort('az')}
            >{$t('notesPage.sortAz')}</button
          >
          <button class="sort-btn" class:active={$sortMode === 'za'} onclick={() => onSetSort('za')}
            >{$t('notesPage.sortZa')}</button
          >
          <div class="sort-divider"></div>
          <button
            class="sort-btn"
            class:active={$sortMode === 'edit-new'}
            onclick={() => onSetSort('edit-new')}
            >{$t('notesPage.sortEditNew')}
            {#if $sortMode === 'edit-new'}✓{/if}</button
          >
          <button
            class="sort-btn"
            class:active={$sortMode === 'edit-old'}
            onclick={() => onSetSort('edit-old')}
            >{$t('notesPage.sortEditOld')}
            {#if $sortMode === 'edit-old'}✓{/if}</button
          >
          <div class="sort-divider"></div>
          <button
            class="sort-btn"
            class:active={$sortMode === 'create-new'}
            onclick={() => onSetSort('create-new')}
            >{$t('notesPage.sortCreateNew')}
            {#if $sortMode === 'create-new'}✓{/if}</button
          >
          <button
            class="sort-btn"
            class:active={$sortMode === 'create-old'}
            onclick={() => onSetSort('create-old')}
            >{$t('notesPage.sortCreateOld')}
            {#if $sortMode === 'create-old'}✓{/if}</button
          >
        </div>
      {/if}
    </div>
    <button
      class="icon-btn"
      title={$allCollapsed ? 'Expandir todo' : 'Comprimir todo'}
      aria-label={$allCollapsed ? 'Expandir todo' : 'Comprimir todo'}
      onclick={toggleCollapseAll}
    >
      <ChevronsUpDown size={13} />
    </button>
  </div>

  <div class="actions-right">
    <button
      class="icon-btn"
      class:active={$viewMode === 'tree'}
      title="Vista de carpetas"
      aria-label="Vista de carpetas"
      onclick={() => {
        $viewMode = 'tree';
        if ($notesPrefsReady) persist();
      }}
    >
      <FolderTree size={13} />
    </button>
    <button
      class="icon-btn"
      class:active={$viewMode === 'list'}
      title="Vista de lista"
      aria-label="Vista de lista"
      onclick={() => {
        $viewMode = 'list';
        if ($notesPrefsReady) persist();
      }}
    >
      <List size={13} />
    </button>
  </div>
</div>

<div class="list-toolbar">
  <div class="search-wrap">
    <Search size={11} style="color: var(--text-muted); flex-shrink:0;" />
    <input class="search-input" bind:value={$search} placeholder={$t('notesPage.search')} />
    {#if $search}
      <button
        class="icon-btn"
        onclick={() => ($search = '')}
        title={$t('notesPage.clear')}
        aria-label={$t('notesPage.clear')}
      >
        <X size={10} />
      </button>
    {/if}
  </div>
  <button
    class="toolbar-btn bulk-toggle"
    class:active={$bulkMode}
    aria-label={$t('notesPage.bulkMode')}
    onclick={() => {
      bulkMode.set(!$bulkMode);
      clearNoteSelection();
    }}
  >
    <SquareCheckBig size={14} />
  </button>
</div>

<div class="list-meta">
  <span
    >{$bulkMode
      ? `${$selectedNoteIds.size} seleccionadas`
      : `${$totalNotes || $notes.length} notas`}</span
  >
  {#if $search}<span class="sep">·</span><span>{$filtered.length} resultados</span>{/if}
  {#if $bulkMode}
    <button
      class="toolbar-btn select-all"
      onclick={$selectedNoteIds.size === $filtered.length ? clearNoteSelection : selectAllNotes}
    >
      {$selectedNoteIds.size === $filtered.length ? 'Deseleccionar todo' : 'Seleccionar todo'}
    </button>
  {/if}
</div>

{#if $bulkMode && $selectedNoteIds.size > 0}
  <div class="bulk-actions">
    <span class="bulk-count"
      >{$selectedNoteIds.size} nota{#if $selectedNoteIds.size !== 1}s{/if}</span
    >
    <button
      class="bulk-btn danger"
      onclick={() => {
        $deleteMode = 'bulk';
        $deleteModalOpen = true;
      }}
    >
      <svg
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        ><polyline points="3 6 5 6 21 6" /><path
          d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
        /></svg
      >
      Eliminar
    </button>
    <button
      class="bulk-btn"
      onclick={() => {
        const t = prompt('Tags a añadir (separadas por coma):');
        if (t)
          tagSelectedNotes(
            t
              .split(',')
              .map((s) => s.trim())
              .filter(Boolean)
          );
      }}
    >
      <svg
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        ><path
          d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"
        /><line x1="7" y1="7" x2="7.01" y2="7" /></svg
      >
      Etiquetar
    </button>
    <button
      class="bulk-btn"
      onclick={() => {
        const t = prompt('Tags a quitar (separadas por coma):');
        if (t)
          untagSelectedNotes(
            t
              .split(',')
              .map((s) => s.trim())
              .filter(Boolean)
          );
      }}
    >
      <svg
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        ><path
          d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"
        /><line x1="7" y1="7" x2="7.01" y2="7" /><line x1="15" y1="9" x2="9" y2="15" /></svg
      >
      Desetiquetar
    </button>
    <button class="bulk-btn" onclick={() => clearNoteSelection()}> Cancelar </button>
  </div>
{/if}

<style>
  .tree-actions-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .actions-left {
    display: flex;
    align-items: center;
    gap: 2px;
  }

  .actions-right {
    display: flex;
    align-items: center;
    gap: 2px;
  }

  .sort-wrapper {
    position: relative;
    display: inline-block;
  }

  .sort-menu {
    position: absolute;
    top: 100%;
    left: 0;
    margin-top: 4px;
    width: 220px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: var(--z-dropdown);
  }

  .sort-btn {
    background: transparent;
    border: none;
    text-align: left;
    padding: 6px 12px;
    font-size: 11px;
    color: var(--text-secondary);
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .sort-btn:hover {
    background: var(--hover);
    color: var(--text-primary);
  }
  .sort-btn.active {
    color: var(--accent);
    font-weight: 500;
  }

  .sort-divider {
    height: 1px;
    background: var(--border-light);
    margin: 4px 0;
  }

  .list-toolbar {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
    flex-shrink: 0;
  }

  .search-wrap {
    display: flex;
    align-items: center;
    gap: 5px;
    flex: 1;
    min-width: 0;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 4px 7px;
  }

  .search-input {
    background: transparent;
    border: none;
    outline: none;
    font-size: 12px;
    font-family: var(--font-sans);
    color: var(--text-primary);
    flex: 1;
    min-width: 0;
  }
  .search-input::placeholder {
    color: var(--text-muted);
  }

  .icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    flex-shrink: 0;
    background: none;
    border: 1px solid transparent;
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .icon-btn:hover {
    background: var(--elevated);
    color: var(--text-secondary);
    border-color: var(--border);
  }
  .icon-btn.active {
    color: var(--text-primary);
    border-color: var(--border);
    background: var(--elevated);
  }

  .toolbar-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    font-size: 11px;
    font-family: var(--font-sans);
    transition: all var(--t-fast);
    flex-shrink: 0;
  }
  .toolbar-btn:hover {
    color: var(--text-primary);
    border-color: var(--text-muted);
  }
  .toolbar-btn.active {
    color: var(--accent);
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 10%, transparent);
  }

  .bulk-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border-bottom: 1px solid var(--border);
    background: var(--elevated);
    flex-shrink: 0;
  }

  .bulk-count {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-primary);
    margin-right: auto;
  }

  .bulk-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    font-size: 11px;
    transition: all var(--t-fast);
  }
  .bulk-btn:hover {
    color: var(--text-primary);
    border-color: var(--text-muted);
  }
  .bulk-btn.danger {
    color: var(--error);
    border-color: color-mix(in srgb, var(--error) 25%, transparent);
  }
  .bulk-btn.danger:hover {
    border-color: var(--error);
    background: color-mix(in srgb, var(--error) 6%, transparent);
  }

  .list-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    border-bottom: 1px solid var(--border-light);
    flex-shrink: 0;
  }
  .sep {
    color: var(--border);
  }

  /* ── Responsive ──
     Restaurado: el bloque completo se perdió en el split #1067. */
  @media (max-width: 768px) {
    .sort-menu {
      width: 180px;
    }
  }

  @media (max-width: 480px) {
    .list-toolbar {
      padding: var(--s1) var(--s2);
    }

    .tree-actions-bar {
      padding: var(--s1) var(--s2);
    }

    .list-meta {
      padding: var(--s1) var(--s2);
    }
  }

  @media (max-width: 360px) {
    .sort-menu {
      width: 130px;
    }
  }
</style>
