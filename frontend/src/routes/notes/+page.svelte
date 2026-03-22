<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { Search, Plus, X, List, FolderTree } from 'lucide-svelte';
  import NoteEditor from '$lib/components/NoteEditor.svelte';
  import FileTree from '$lib/components/FileTree.svelte';
  import NoteCard from '$lib/components/NoteCard.svelte';
  import { notes, notesLoading, loadNotes, createNote, updateNote, deleteNote, aiSuggestions } from '$lib/stores/notes';
  import { buildTree } from '$lib/utils/fileTree';
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

  // Tree collapse state — centralized Set of collapsed paths
  let collapsed = new Set<string>();

  $: showNew = $page.url.searchParams.get('new') === '1';
  $: selectedId = $page.url.searchParams.get('id');

  // Tree data recomputed when notes or search changes
  $: tree = buildTree($notes, viewMode === 'tree' ? search : '');

  // Flat filtered list for list mode
  $: filtered = $notes.filter(n =>
    !search ||
    n.title.toLowerCase().includes(search.toLowerCase()) ||
    n.tags.some(t => t.includes(search.toLowerCase()))
  );

  onMount(async () => {
    // Restore saved panel width
    const saved = localStorage.getItem('notes-panel-w');
    if (saved) panelWidth = Math.max(MIN_W, Math.min(MAX_W, parseInt(saved)));

    await loadNotes();
    if (showNew) openNew();
    if (selectedId) {
      const n = $notes.find(n => String(n.id) === selectedId);
      if (n) openNote(n);
    }
  });

  // ── Resize handle ────────────────────────────────────────────────────────────
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

  // Bubble collapse toggle from FileTree to trigger Svelte reactivity
  function onToggle() {
    collapsed = collapsed; // reassign to trigger reactive $: tree update
  }
</script>

<div
  class="notes-page"
  class:dragging
  style="--panel-w: {panelWidth}px"
>
  <!-- ── List / Tree panel ─────────────────────────────────────────────────── -->
  <aside class="notes-list">
    <!-- Toolbar -->
    <div class="list-toolbar">
      <div class="search-wrap">
        <Search size={11} style="color: var(--text-muted); flex-shrink:0;" />
        <input
          class="search-input"
          bind:value={search}
          placeholder="Buscar..."
        />
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

    <!-- Count -->
    <div class="list-meta">
      <span>{$notes.length} notas</span>
      {#if search}<span class="sep">·</span><span>{filtered.length} resultados</span>{/if}
    </div>

    <!-- Content -->
    <div class="list-scroll">
      {#if $notesLoading}
        <div class="empty-msg">Cargando...</div>
      {:else if viewMode === 'tree'}
        {#if tree.length === 0}
          <div class="empty-msg">{search ? 'Sin resultados.' : 'Sin notas.'}</div>
        {:else}
          <div class="tree-wrap">
            <FileTree
              nodes={tree}
              {collapsed}
              selectedNoteId={selectedNote?.id ?? null}
              on:select={(e) => openNote(e.detail)}
              on:toggle={onToggle}
            />
          </div>
        {/if}
      {:else}
        {#if filtered.length === 0}
          <div class="empty-msg">{search ? 'Sin resultados.' : 'Sin notas.'}</div>
        {:else}
          {#each filtered as note}
            <NoteCard
              {note}
              active={selectedNote?.id === note.id}
              on:select={(e) => openNote(e.detail)}
            />
          {/each}
        {/if}
      {/if}
    </div>
  </aside>

  <!-- ── Resize handle ─────────────────────────────────────────────────────── -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="resize-handle" on:mousedown={startResize} title="Arrastrar para redimensionar"></div>

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

  /* Prevent text selection while dragging */
  .notes-page.dragging { user-select: none; cursor: col-resize; }
  .notes-page.dragging * { cursor: col-resize; }

  /* ── Left panel ── */
  .notes-list {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    border-right: none; /* border is on the handle */
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
  .icon-btn:hover { background: var(--elevated); color: var(--text-secondary); border-color: var(--border); }
  .icon-btn.active { color: var(--text-primary); border-color: var(--border); background: var(--elevated); }

  .new-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    flex-shrink: 0;
    background: var(--accent);
    border: none;
    border-radius: var(--r);
    color: var(--bg);
    cursor: pointer;
    transition: opacity var(--t-fast);
  }
  .new-btn:hover { opacity: 0.85; }

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
  .sep { color: var(--border); }

  .list-scroll {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
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

  /* ── Resize handle ── */
  .resize-handle {
    background: var(--border-light);
    cursor: col-resize;
    transition: background var(--t-fast);
    position: relative;
    z-index: 1;
  }
  .resize-handle:hover,
  .notes-page.dragging .resize-handle {
    background: var(--text-muted);
  }
  /* Wider invisible hit area */
  .resize-handle::after {
    content: '';
    position: absolute;
    inset: 0 -4px;
  }

  /* ── Editor panel ── */
  .editor-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    background: var(--bg);
    min-width: 0;
  }

  .empty-editor {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    font-size: 12px;
  }
</style>
