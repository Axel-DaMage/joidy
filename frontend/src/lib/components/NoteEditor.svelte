<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import TagChip from './TagChip.svelte';
  import { aiSuggestions, fetchAISuggestions } from '$lib/stores/notes';
  import type { Note } from '$lib/api';

  export let note: Note | null = null; // null = new note

  let title = note?.title ?? '';
  let content = note?.content ?? '';
  let tags: string[] = note?.tags ?? [];
  let tagInput = '';
  let saving = false;
  let aiTimeout: ReturnType<typeof setTimeout>;

  const dispatch = createEventDispatcher<{ save: { title: string; content: string; tags: string[] }; cancel: void; delete: void }>();

  function addTag(t: string) {
    const clean = t.trim().toLowerCase();
    if (clean && !tags.includes(clean)) {
      tags = [...tags, clean];
    }
    tagInput = '';
  }

  function removeTag(t: string) {
    tags = tags.filter(x => x !== t);
  }

  function onTagKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag(tagInput);
    } else if (e.key === 'Backspace' && tagInput === '' && tags.length > 0) {
      tags = tags.slice(0, -1);
    }
  }

  function onContentChange() {
    if (!note || content.length < 20) return;
    clearTimeout(aiTimeout);
    aiTimeout = setTimeout(() => {
      if (note) fetchAISuggestions(note.id, content, tags);
    }, 2000);
  }

  function acceptSuggestion(tag: string) {
    addTag(tag);
    aiSuggestions.update(s => s.filter(x => x.tag !== tag));
  }

  function dismissSuggestion(tag: string) {
    aiSuggestions.update(s => s.filter(x => x.tag !== tag));
  }

  async function handleSave() {
    if (!title.trim()) return;
    saving = true;
    dispatch('save', { title: title.trim(), content, tags });
    saving = false;
  }
</script>

<div class="editor">
  <div class="editor-header">
    <input
      class="title-input"
      bind:value={title}
      placeholder="Título de la nota..."
      on:keydown={(e) => e.key === 'Enter' && handleSave()}
    />
  </div>

  <textarea
    class="input content-input"
    bind:value={content}
    on:input={onContentChange}
    placeholder="Escribe en markdown..."
    rows="10"
  ></textarea>

  <!-- Tags -->
  <div class="tags-section">
    <div class="tags-row">
      {#each tags as tag}
        <TagChip {tag} removable on:remove={(e) => removeTag(e.detail)} />
      {/each}
      <input
        class="tag-input"
        bind:value={tagInput}
        on:keydown={onTagKeydown}
        placeholder="agregar tag..."
      />
    </div>

    <!-- AI suggestions -->
    {#if $aiSuggestions.length > 0}
      <div class="ai-suggestions">
        <span class="label" style="margin-right: 6px;">ia sugiere:</span>
        {#each $aiSuggestions as s}
          <button class="suggestion-btn" on:click={() => acceptSuggestion(s.tag)}>
            + {s.tag}
            <span class="conf">{Math.round(s.confidence * 100)}%</span>
          </button>
          <button class="dismiss-btn" on:click={() => dismissSuggestion(s.tag)}>×</button>
        {/each}
      </div>
    {/if}
  </div>

  <div class="editor-actions">
    <button class="btn btn-primary" on:click={handleSave} disabled={saving || !title.trim()}>
      {saving ? 'Guardando...' : note ? 'Guardar' : 'Crear nota'}
    </button>
    <button class="btn btn-ghost" on:click={() => dispatch('cancel')}>Cancelar</button>
    {#if note}
      <button class="btn btn-ghost" style="color: var(--error); margin-left: auto;" on:click={() => dispatch('delete')}>
        Eliminar
      </button>
    {/if}
  </div>
</div>

<style>
  .editor {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    padding: var(--s4);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
  }

  .title-input {
    background: transparent;
    border: none;
    outline: none;
    font-size: 16px;
    font-weight: 400;
    color: var(--text-primary);
    font-family: var(--font-sans);
    width: 100%;
    padding: 0;
    border-bottom: 1px solid var(--border);
    padding-bottom: var(--s2);
  }

  .title-input::placeholder { color: var(--text-muted); }

  .content-input {
    min-height: 160px;
    font-size: 13px;
  }

  .tags-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
    padding: var(--s2) 0;
    border-top: 1px solid var(--border-light);
  }

  .tag-input {
    background: transparent;
    border: none;
    outline: none;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-secondary);
    min-width: 100px;
  }

  .tag-input::placeholder { color: var(--text-muted); }

  .ai-suggestions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px;
    padding-top: var(--s2);
  }

  .suggestion-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border: 1px solid var(--xp);
    border-radius: 2px;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--xp);
    background: transparent;
    cursor: pointer;
    transition: background var(--t-normal);
  }
  .suggestion-btn:hover { background: color-mix(in srgb, var(--xp) 10%, transparent); }

  .conf {
    font-size: 9px;
    opacity: 0.7;
  }

  .dismiss-btn {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 14px;
    line-height: 1;
    padding: 0 2px;
    margin-left: -4px;
  }
  .dismiss-btn:hover { color: var(--text-secondary); }

  .editor-actions {
    display: flex;
    gap: var(--s2);
    padding-top: var(--s2);
    border-top: 1px solid var(--border-light);
  }
</style>
