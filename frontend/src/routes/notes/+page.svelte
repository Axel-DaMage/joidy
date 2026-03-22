<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { Search, Plus, X } from 'lucide-svelte';
  import NoteCard from '$lib/components/NoteCard.svelte';
  import NoteEditor from '$lib/components/NoteEditor.svelte';
  import { notes, notesLoading, loadNotes, createNote, updateNote, deleteNote, aiSuggestions } from '$lib/stores/notes';
  import type { Note } from '$lib/api';

  let search = '';
  let selectedNote: Note | null = null;
  let showEditor = false;
  let editingNew = false;

  $: showNew = $page.url.searchParams.get('new') === '1';
  $: selectedId = $page.url.searchParams.get('id');

  $: filtered = $notes.filter(n =>
    !search ||
    n.title.toLowerCase().includes(search.toLowerCase()) ||
    n.tags.some(t => t.includes(search.toLowerCase()))
  );

  onMount(async () => {
    await loadNotes();
    if (showNew) { openNew(); }
    if (selectedId) {
      const n = $notes.find(n => String(n.id) === selectedId);
      if (n) openNote(n);
    }
  });

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

<div class="notes-page">
  <!-- List panel -->
  <aside class="notes-list">
    <div class="list-toolbar">
      <div class="search-wrap">
        <Search size={12} style="color: var(--text-muted); flex-shrink:0;" />
        <input class="search-input" bind:value={search} placeholder="Buscar notas..." />
        {#if search}
          <button class="btn btn-ghost btn-icon" style="width:20px;height:20px;" on:click={() => search = ''}>
            <X size={10} />
          </button>
        {/if}
      </div>
      <button class="btn btn-primary" style="padding: 4px 10px; font-size:12px; white-space:nowrap;" on:click={openNew}>
        <Plus size={12} />
      </button>
    </div>

    <div class="list-count caption" style="padding: 6px 16px;">
      {filtered.length} nota{filtered.length !== 1 ? 's' : ''}
    </div>

    {#if $notesLoading}
      <div style="padding: 32px; text-align:center; color: var(--text-muted); font-size:12px;">Cargando...</div>
    {:else if filtered.length === 0}
      <div style="padding: 32px; text-align:center; color: var(--text-muted); font-size:12px;">
        {search ? 'Sin resultados.' : 'Sin notas. Crea la primera.'}
      </div>
    {:else}
      {#each filtered as note}
        <NoteCard {note} active={selectedNote?.id === note.id} on:select={(e) => openNote(e.detail)} />
      {/each}
    {/if}
  </aside>

  <!-- Editor panel — full height, no padding wrapper -->
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
    grid-template-columns: 260px 1fr;
    height: 100%;
    overflow: hidden;
  }

  .notes-list {
    border-right: 1px solid var(--border);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .list-toolbar {
    display: flex;
    align-items: center;
    gap: var(--s2);
    padding: var(--s3) var(--s4);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    background: var(--bg);
    z-index: 1;
  }

  .search-wrap {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 4px 8px;
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

  .editor-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    background: var(--bg);
  }

  .empty-editor {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
  }
</style>
