<script lang="ts">
  import { noteSearchQuery, noteSearchTag, filteredNotes, notes } from '$lib/stores/notes';
  import { derived } from 'svelte/store';
  import { api } from '$lib/api';
  import type { Note } from '$lib/api';

  let searchInput = '';
  let semanticMode = $state(false);
  let semanticResults = $state<{ note: Note; score: number }[]>([]);
  let semanticLoading = $state(false);
  let semanticAbort: AbortController | null = null;

  // In textual mode, feed the query into the store for client-side filtering.
  // In semantic mode, query the API and bypass the store filter.
  $effect(() => {
    if (!semanticMode) {
      noteSearchQuery.set(searchInput);
    } else {
      noteSearchQuery.set(''); // clear text filter so semantic results show
      void runSemanticSearch(searchInput);
    }
  });

  async function runSemanticSearch(query: string) {
    if (semanticAbort) semanticAbort.abort();
    if (!query.trim()) {
      semanticResults = [];
      return;
    }
    semanticAbort = new AbortController();
    semanticLoading = true;
    try {
      const resp = await api.notes.semanticSearch(query, 10, 0.5, );
      semanticResults = resp.results;
    } catch {
      semanticResults = [];
    } finally {
      semanticLoading = false;
    }
  }

  const allTags = derived(notes, $notes => {
    const tags = new Set<string>();
    $notes.forEach(n => n.tags.forEach(t => tags.add(t)));
    return Array.from(tags).sort();
  });

  function clearSearch() {
    searchInput = '';
    semanticResults = [];
    noteSearchQuery.set('');
    noteSearchTag.set(null);
  }
</script>

<div class="note-search">
  <div class="search-row">
    <input
      type="text"
      class="search-input"
      placeholder={semanticMode ? 'Búsqueda semántica...' : 'Buscar notas...'}
      bind:value={searchInput}
    />
    <button
      class="mode-toggle"
      class:active={semanticMode}
      onclick={() => { semanticMode = !semanticMode; if (!semanticMode) semanticResults = []; }}
      title="Alternar búsqueda semántica (por significado, no por texto exacto)"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
      </svg>
    </button>
    {#if searchInput || $noteSearchTag}
      <button class="clear-btn" onclick={clearSearch}>✕</button>
    {/if}
  </div>

  {#if semanticMode && semanticLoading}
    <div class="semantic-status caption">Buscando semánticamente...</div>
  {/if}
  {#if semanticMode && semanticResults.length > 0}
    <div class="semantic-results">
      {#each semanticResults as result}
        <button
          class="semantic-result"
          onclick={() => {
            // Select the note in the list by setting the tag filter to null
            // and scrolling — the parent handles selection via filteredNotes.
            noteSearchTag.set(null);
          }}
        >
          <span class="semantic-title">{result.note.title}</span>
          <span class="semantic-score">{(result.score * 100).toFixed(0)}%</span>
        </button>
      {/each}
    </div>
  {/if}

  {#if !semanticMode && $allTags.length > 0}
    <div class="tag-filter">
      <button
        class="tag-chip"
        class:active={$noteSearchTag === null}
        onclick={() => noteSearchTag.set(null)}
      >
        Todo
      </button>
      {#each $allTags.slice(0, 8) as tag}
        <button
          class="tag-chip"
          class:active={$noteSearchTag === tag}
          onclick={() => noteSearchTag.set($noteSearchTag === tag ? null : tag)}
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

  .mode-toggle {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    padding: 6px;
    display: flex;
    align-items: center;
    transition: all var(--t-fast);
  }

  .mode-toggle:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .mode-toggle.active {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
  }

  .semantic-status {
    padding: 4px 8px;
    color: var(--text-muted);
    font-size: 11px;
  }

  .semantic-results {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 300px;
    overflow-y: auto;
  }

  .semantic-result {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 10px;
    border: 1px solid var(--border-light);
    border-radius: var(--r);
    background: var(--elevated);
    color: var(--text-primary);
    cursor: pointer;
    font-size: 12px;
    text-align: left;
    transition: all var(--t-fast);
  }

  .semantic-result:hover {
    border-color: var(--accent);
    background: var(--hover);
  }

  .semantic-title {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .semantic-score {
    color: var(--xp);
    font-family: var(--font-mono);
    font-size: 11px;
    margin-left: 8px;
  }
</style>