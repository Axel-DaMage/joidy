<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { Search, Plus, X, List, FolderTree, ChevronRight } from 'lucide-svelte';
  import NoteEditor from '$lib/components/NoteEditor.svelte';
  import NoteCard from '$lib/components/NoteCard.svelte';
  import { notes, notesLoading, loadNotes, createNote, updateNote, deleteNote, aiSuggestions } from '$lib/stores/notes';
  import { buildTree, flattenTree } from '$lib/utils/fileTree';
  import type { Note } from '$lib/api';

  // ── State ────────────────────────────────────────────────────────────────────
  let search = '';
  let selectedNote: Note | null = null;
  let showEditor = false;
  let editingNew = false;
  let viewMode: 'tree' | 'list' = 'tree';

  // Resizable panel
  const MIN_W = 160;
  const MAX_W = 520;
  let panelWidth = 260;
  let dragging = false;

  // Tree collapse state — Set of collapsed folder paths
  let collapsed = new Set<string>();

  $: showNew = $page.url.searchParams.get('new') === '1';
  $: selectedId = $page.url.searchParams.get('id');

  // Flat filtered list for list mode
  $: filtered = $notes.filter(n =>
    !search ||
    n.title.toLowerCase().includes(search.toLowerCase()) ||
    n.tags.some(t => t.includes(search.toLowerCase()))
  );

  // Tree → flat list (no recursive component, avoids Svelte 5 HMR issues)
  $: tree = buildTree($notes, viewMode === 'tree' ? search : '');
  $: flatNodes = flattenTree(tree, collapsed);

  onMount(async () => {
    const saved = localStorage.getItem('notes-panel-w');
    if (saved) panelWidth = Math.max(MIN_W, Math.min(MAX_W, parseInt(saved)));
    await loadNotes();
    if (showNew) openNew();
    if (selectedId) {
      const n = $notes.find(n => String(n.id) === selectedId);
      if (n) openNote(n);
    }
  });

  // ── Resize ───────────────────────────────────────────────────────────────────
  function startResize(e: MouseEvent) {
    e.preventDefault();
    dragging = true;
    const startX = e.clientX;
    const startW = panelWidth;
    function onMove(e: MouseEvent) {
      panelWidth = Math.max(MIN_W, Math.min(MAX_W, startW + (e.clientX - startX)));
    }
    function onUp() {
      dragging = false;
      localStorage.setItem('notes-panel-w', String(panelWidth));
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }

  // ── Tree toggle ──────────────────────────────────────────────────────────────
  function toggleFolder(path: string) {
    if (collapsed.has(path)) collapsed.delete(path);
    else collapsed.add(path);
    collapsed = collapsed; // trigger reactivity
  }

  // ── Note actions ─────────────────────────────────────────────────────────────
  function openNote(note: Note) {
    selectedNote = note;
    showEditor = true;
    editingNew = false;
    aiSuggestions.set([]);
  }

  function openNew() {
    selectedNote = null;
    showEditor = true;
    editingNew = true;
    aiSuggestions.set([]);
  }

  function closeEditor() {
    showEditor = false;
    selectedNote = null;
    goto('/notes');
  }

  async function handleSave(e: CustomEvent<{ title: string; content: string; tags: string[] }>) {
    const { title, content, tags } = e.detail;
    if (editingNew) {
      const n = await createNote(title, content, tags);
      if (n) { selectedNote = n; editingNew = false; }
    } else if (selectedNote) {
      await updateNote(selectedNote.id, { title, content, tags });
    }
  }

  async function handleDelete() {
    if (selectedNote) {
      await deleteNote(selectedNote.id);
      closeEditor();
    }
  }
</script>

<div
  class="notes-page"
  class:dragging
  style="--panel-w: {panelWidth}px"
>
  <!-- ── List / Tree panel ─────────────────────────────────────────────────── -->
  <aside class="notes-list">
    <div class="list-toolbar">
      <div class="search-wrap">
        <Search size={11} style="color: var(--text-muted); flex-shrink:0;" />
        <input class="search-input" bind:value={search} placeholder="Buscar..." />
        {#if search}
          <button class="icon-btn" on:click={() => search = ''} title="Limpiar">
            <X size={10} />
          </button>
        {/if}
      </div>
      <button
        class="icon-btn"
        class:active={viewMode === 'tree'}
        on:click={() => viewMode = viewMode === 'tree' ? 'list' : 'tree'}
        title={viewMode === 'tree' ? 'Vista lista' : 'Vista árbol'}
      >
        {#if viewMode === 'tree'}<List size={13} />{:else}<FolderTree size={13} />{/if}
      </button>
      <button class="new-btn" on:click={openNew} title="Nueva nota">
        <Plus size={13} />
      </button>
    </div>

    <div class="list-meta">
      <span>{$notes.length} notas</span>
      {#if search}<span class="sep">·</span><span>{filtered.length} resultados</span>{/if}
    </div>

    <div class="list-scroll">
      {#if $notesLoading}
        <div class="empty-msg">Cargando...</div>

      {:else if viewMode === 'tree'}
        {#if flatNodes.length === 0}
          <div class="empty-msg">{search ? 'Sin resultados.' : 'Sin notas.'}</div>
        {:else}
          <div class="tree-wrap">
            {#each flatNodes as node (node.path)}
              {#if node.type === 'folder'}
                <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
                <div
                  class="tree-row folder-row"
                  style="padding-left: {8 + node.depth * 14}px"
                  on:click={() => toggleFolder(node.path)}
                >
                  <span class="chevron" class:open={!collapsed.has(node.path)}>
                    <ChevronRight size={11} />
                  </span>
                  <span class="t-icon">{node.icon}</span>
                  <span class="t-name folder-name">{node.name}</span>
                  <span class="t-count">{node.childCount}</span>
                </div>
              {:else}
                <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
                <div
                  class="tree-row file-row"
                  class:active={node.note?.id === selectedNote?.id}
                  style="padding-left: {20 + node.depth * 14}px"
                  on:click={() => node.note && openNote(node.note)}
                >
                  <span class="t-icon file-icon">{node.icon}</span>
                  <span class="t-name file-name">{node.name}</span>
                </div>
              {/if}
            {/each}
          </div>
        {/if}

      {:else}
        {#if filtered.length === 0}
          <div class="empty-msg">{search ? 'Sin resultados.' : 'Sin notas.'}</div>
        {:else}
          {#each filtered as note}
            <NoteCard {note} active={selectedNote?.id === note.id} on:select={(e) => openNote(e.detail)} />
          {/each}
        {/if}
      {/if}
    </div>
  </aside>

  <!-- ── Resize handle ─────────────────────────────────────────────────────── -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="resize-handle" on:mousedown={startResize}></div>

  <!-- ── Editor panel ──────────────────────────────────────────────────────── -->
  <div class="editor-panel">
    {#if showEditor}
      <NoteEditor
        note={editingNew ? null : selectedNote}
        on:save={handleSave}
        on:cancel={closeEditor}
        on:delete={handleDelete}
      />
    {:else}
      <div class="empty-editor">
        <span class="caption">Selecciona una nota o crea una nueva</span>
      </div>
    {/if}
  </div>
</div>

<style>
  .notes-page {
    display: grid;
    grid-template-columns: var(--panel-w) 5px 1fr;
    height: 100%;
    overflow: hidden;
  }
  .notes-page.dragging { user-select: none; }
  .notes-page.dragging * { cursor: col-resize !important; }

  /* ── Panel ── */
  .notes-list {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    min-width: 0;
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
  .search-input::placeholder { color: var(--text-muted); }

  .icon-btn {
    display: flex; align-items: center; justify-content: center;
    width: 26px; height: 26px; flex-shrink: 0;
    background: none; border: 1px solid transparent;
    border-radius: var(--r); color: var(--text-muted); cursor: pointer;
    transition: all var(--t-fast);
  }
  .icon-btn:hover { background: var(--elevated); color: var(--text-secondary); border-color: var(--border); }
  .icon-btn.active { color: var(--text-primary); border-color: var(--border); background: var(--elevated); }

  .new-btn {
    display: flex; align-items: center; justify-content: center;
    width: 26px; height: 26px; flex-shrink: 0;
    background: var(--accent); border: none; border-radius: var(--r);
    color: var(--bg); cursor: pointer; transition: opacity var(--t-fast);
  }
  .new-btn:hover { opacity: 0.8; }

  .list-meta {
    display: flex; align-items: center; gap: 6px;
    padding: 5px 12px;
    font-size: 10px; font-family: var(--font-mono); color: var(--text-muted);
    border-bottom: 1px solid var(--border-light); flex-shrink: 0;
  }
  .sep { color: var(--border); }

  .list-scroll { flex: 1; overflow-y: auto; overflow-x: hidden; }

  .tree-wrap { padding: 4px 0; }

  .empty-msg {
    padding: 32px 16px; text-align: center;
    color: var(--text-muted); font-size: 12px;
  }

  /* ── Tree rows ── */
  .tree-row {
    display: flex; align-items: center; gap: 5px;
    padding-right: 8px; height: 26px;
    cursor: pointer; user-select: none;
    border-radius: 3px; margin: 0 4px;
    transition: background var(--t-fast);
    min-width: 0;
  }
  .tree-row:hover { background: var(--hover); }
  .file-row.active { background: var(--elevated); }

  .chevron {
    color: var(--text-muted); display: flex; align-items: center;
    flex-shrink: 0; transition: transform var(--t-fast);
  }
  .chevron.open { transform: rotate(90deg); }

  .t-icon { font-size: 12px; line-height: 1; flex-shrink: 0; width: 16px; text-align: center; }
  .file-icon { font-size: 11px; }

  .t-name {
    font-size: 12px; font-family: var(--font-sans);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    flex: 1; min-width: 0; color: var(--text-secondary);
  }
  .file-row.active .t-name { color: var(--text-primary); }

  .t-count {
    font-size: 10px; font-family: var(--font-mono);
    color: var(--text-muted); flex-shrink: 0;
  }

  /* ── Resize handle ── */
  .resize-handle {
    background: var(--border-light); cursor: col-resize;
    transition: background var(--t-fast); position: relative; z-index: 1;
  }
  .resize-handle:hover,
  .notes-page.dragging .resize-handle { background: var(--text-muted); }
  .resize-handle::after {
    content: ''; position: absolute; inset: 0 -4px;
  }

  /* ── Editor ── */
  .editor-panel {
    display: flex; flex-direction: column;
    height: 100%; overflow: hidden;
    background: var(--bg); min-width: 0;
  }
  .empty-editor {
    display: flex; align-items: center; justify-content: center;
    height: 100%; color: var(--text-muted); font-size: 12px;
  }
</style>
