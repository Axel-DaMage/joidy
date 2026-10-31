<script lang="ts">
  import type { Note } from '$lib/api';
  import { FilePlus2, Search, X } from 'lucide-svelte';
  import { _ } from 'svelte-i18n';

  let {
    notes = [],
    value = $bindable(null),
    id = undefined,
    placeholder = '',
    onCreateNote,
  }: {
    notes?: Note[];
    value?: number | null;
    id?: string;
    placeholder?: string;
    onCreateNote?: (title: string) => void | Promise<void>;
  } = $props();

  let query = $state('');
  let open = $state(false);
  let highlight = $state(0);
  let container: HTMLDivElement | undefined = $state();

  const selected = $derived(notes.find((n) => n.id === value) ?? null);
  const q = $derived(query.trim().toLowerCase());

  // Ordered: exact title matches first, then the rest (recent notes first as
  // the API returns them newest-first).
  const results = $derived.by(() => {
    const pool = q
      ? notes.filter((n) => n.title.toLowerCase().includes(q))
      : notes;
    return pool.slice(0, 8);
  });

  const hasExactMatch = $derived(
    !!q && notes.some((n) => n.title.trim().toLowerCase() === q)
  );
  const canCreate = $derived(!!q && !hasExactMatch && !!onCreateNote);

  function pick(note: Note) {
    value = note.id;
    query = '';
    open = false;
  }

  function clear() {
    value = null;
    query = '';
  }

  function create() {
    if (!canCreate || !onCreateNote) return;
    onCreateNote(query.trim());
    query = '';
    open = false;
  }

  function handleKeydown(e: KeyboardEvent) {
    const max = results.length + (canCreate ? 1 : 0);
    if (e.key === 'Escape') {
      open = false;
      query = '';
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      open = true;
      highlight = (highlight + 1) % Math.max(max, 1);
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      highlight = (highlight - 1 + Math.max(max, 1)) % Math.max(max, 1);
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      if (canCreate && highlight >= results.length) {
        create();
      } else if (results[highlight]) {
        pick(results[highlight]);
      }
    }
  }

  function onWindowPointerDown(e: PointerEvent) {
    if (container && !container.contains(e.target as Node)) open = false;
  }
</script>

<svelte:window onpointerdown={onWindowPointerDown} />

{#if selected}
  <div class="nlp-selected">
    <span class="nlp-selected-title">{selected.title}</span>
    <button
      type="button"
      class="nlp-clear"
      onclick={clear}
      aria-label={$_('goalsPage.noLinkedNote')}
    >
      <X size={14} />
    </button>
  </div>
{:else}
  <div
    class="nlp-picker"
    bind:this={container}
    role="combobox"
    aria-controls="nlp-list-{id}"
    aria-expanded={open}
  >
    <div class="nlp-input-row">
      <Search size={14} />
      <input
        {id}
        type="text"
        bind:value={query}
        {placeholder}
        onfocus={() => (open = true)}
        oninput={() => {
          open = true;
          highlight = 0;
        }}
        onkeydown={handleKeydown}
        autocomplete="off"
      />
    </div>
    {#if open}
      <div class="nlp-list" role="listbox" id="nlp-list-{id}">
        {#each results as note, i (note.id)}
          <button
            type="button"
            role="option"
            aria-selected={value === note.id}
            class="nlp-option"
            class:active={i === highlight}
            onpointerdown={() => pick(note)}
            onmouseenter={() => (highlight = i)}
          >
            {note.title}
          </button>
        {:else}
          <div class="nlp-empty">{$_('goalsPage.noNotesMatch')}</div>
        {/each}
        {#if canCreate}
          <button
            type="button"
            class="nlp-option nlp-create"
            class:active={highlight >= results.length}
            onpointerdown={create}
            onmouseenter={() => (highlight = results.length)}
          >
            <FilePlus2 size={14} />
            {$_('goalsPage.createNote')} “{query.trim()}”
          </button>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .nlp-picker {
    position: relative;
  }
  .nlp-input-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--surface-hover);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-muted);
  }
  .nlp-input-row input {
    flex: 1;
    min-width: 0;
    border: none;
    background: transparent;
    color: var(--text);
    font-size: 14px;
    outline: none;
  }
  .nlp-list {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    right: 0;
    z-index: 30;
    max-height: 240px;
    overflow-y: auto;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  }
  .nlp-option {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 12px;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    font-size: 13px;
    text-align: left;
    cursor: pointer;
    max-width: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .nlp-option.active {
    background: rgba(var(--primary-rgb, 139, 92, 246), 0.1);
    color: var(--primary);
  }
  .nlp-create {
    border-top: 1px solid var(--border);
  }
  .nlp-empty {
    padding: 8px 12px;
    font-size: 12px;
    color: var(--text-muted);
  }
  .nlp-selected {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    max-width: 100%;
    padding: 6px 10px;
    background: rgba(var(--primary-rgb, 139, 92, 246), 0.1);
    border: 1px solid var(--primary);
    border-radius: 999px;
    color: var(--primary);
  }
  .nlp-selected-title {
    font-size: 13px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .nlp-clear {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 2px;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: inherit;
    cursor: pointer;
    flex-shrink: 0;
  }
  .nlp-clear:hover {
    background: rgba(var(--primary-rgb, 139, 92, 246), 0.2);
  }
</style>
