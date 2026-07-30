<script lang="ts">
  import { Search } from 'lucide-svelte';

  let {
    query = $bindable(''),
    filter = $bindable<string | null>(null)
  } = $props();
</script>

<div class="editor-header">
  <h3 class="editor-title">Editor de Objetivos</h3>
  <div class="editor-controls">
    <div class="search-box">
      <Search size={16} />
      <input
        type="text"
        placeholder="Buscar objetivos..."
        bind:value={query}
      />
    </div>
    <div class="filter-buttons">
      <button
        class="filter-btn"
        class:active={filter === null}
        onclick={() => filter = null}
      >Todos</button>
      <button
        class="filter-btn"
        class:active={filter === 'PINNED'}
        onclick={() => filter = 'PINNED'}
      >Fijados</button>
      <button
        class="filter-btn"
        class:active={filter === 'ACTIVE'}
        onclick={() => filter = 'ACTIVE'}
      >Activos</button>
      <button
        class="filter-btn"
        class:active={filter === 'COMPLETED'}
        onclick={() => filter = 'COMPLETED'}
      >Completados</button>
      <button
        class="filter-btn"
        class:active={filter === 'PAUSED'}
        onclick={() => filter = 'PAUSED'}
      >Pausados</button>
      <button
        class="filter-btn"
        class:active={filter === 'FAILED'}
        onclick={() => filter = 'FAILED'}
      >Fallidos</button>
    </div>
  </div>
</div>

<style>
  .editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 24px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
    gap: 20px;
    flex-wrap: wrap;
  }

  .editor-title {
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  .editor-controls {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }

  .search-box {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    background: var(--surface-hover);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-muted);
  }

  .search-box input {
    background: transparent;
    border: none;
    color: var(--text-primary);
    font-size: 13px;
    outline: none;
    width: 180px;
  }

  .search-box input::placeholder {
    color: var(--text-muted);
  }

  .filter-buttons {
    display: flex;
    gap: 6px;
  }

  .filter-btn {
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .filter-btn:hover {
    background: var(--surface-hover);
    color: var(--text-primary);
  }

  .filter-btn.active {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
    font-weight: 500;
  }

  @media (max-width: 768px) {
    .editor-header {
      flex-direction: column;
      gap: 12px;
      align-items: flex-start;
    }
  }
</style>
