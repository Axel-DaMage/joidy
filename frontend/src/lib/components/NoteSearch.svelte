<script lang="ts">
  import { noteSearchQuery, noteSearchTag, filteredNotes, notes } from '$lib/stores/notes';
  import { derived } from 'svelte/store';

  let searchInput = '';

  $: noteSearchQuery.set(searchInput);

  const allTags = derived(notes, $notes => {
    const tags = new Set<string>();
    $notes.forEach(n => n.tags.forEach(t => tags.add(t)));
    return Array.from(tags).sort();
  });

  function clearSearch() {
    searchInput = '';
    noteSearchQuery.set('');
    noteSearchTag.set(null);
  }
</script>

<div class="note-search">
  <div class="search-row">
    <input
      type="text"
      class="search-input"
      placeholder="Buscar notas..."
      bind:value={searchInput}
    />
    {#if searchInput || $noteSearchTag}
      <button class="clear-btn" on:click={clearSearch}>✕</button>
    {/if}
  </div>

  {#if $allTags.length > 0}
    <div class="tag-filter">
      <button
        class="tag-chip"
        class:active={$noteSearchTag === null}
        on:click={() => noteSearchTag.set(null)}
      >
        Todo
      </button>
      {#each $allTags.slice(0, 8) as tag}
        <button
          class="tag-chip"
          class:active={$noteSearchTag === tag}
          on:click={() => noteSearchTag.set($noteSearchTag === tag ? null : tag)}
        >
          {tag}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .note-search {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 8px 0;
  }

  .search-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .search-input {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--elevated);
    color: var(--text-primary);
    font-size: 13px;
    outline: none;
  }

  .search-input:focus {
    border-color: var(--accent);
  }

  .search-input::placeholder {
    color: var(--text-muted);
  }

  .clear-btn {
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 4px;
    font-size: 14px;
  }

  .clear-btn:hover {
    color: var(--text-primary);
  }

  .tag-filter {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .tag-chip {
    padding: 4px 10px;
    font-size: 11px;
    border-radius: 12px;
    border: 1px solid var(--border-light);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--t-fast);
  }

  .tag-chip:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .tag-chip.active {
    background: var(--accent);
    border-color: var(--accent);
    color: white;
  }
</style>