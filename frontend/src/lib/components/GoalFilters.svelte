<script lang="ts">
  import { Search } from 'lucide-svelte';
  import { t } from 'svelte-i18n';

  let {
    query = $bindable(''),
    filter = $bindable<string | null>(null)
  } = $props();
</script>

<div class="editor-header">
  <h3 class="editor-title">{$t('goalFilters.editorTitle')}</h3>
  <div class="editor-controls">
    <div class="search-box">
      <Search size={16} />
      <input
        type="text"
        placeholder={$t('goalFilters.searchPlaceholder')}
        bind:value={query}
      />
    </div>
    <div class="filter-buttons">
      <button
        class="filter-btn"
        class:active={filter === null}
        onclick={() => filter = null}
      >{$t('goalFilters.all')}</button>
      <button
        class="filter-btn"
        class:active={filter === 'PINNED'}
        onclick={() => filter = 'PINNED'}
      >{$t('goalFilters.pinned')}</button>
      <button
        class="filter-btn"
        class:active={filter === 'ACTIVE'}
        onclick={() => filter = 'ACTIVE'}
      >{$t('goalFilters.active')}</button>
      <button
        class="filter-btn"
        class:active={filter === 'COMPLETED'}
        onclick={() => filter = 'COMPLETED'}
      >{$t('goalFilters.completed')}</button>
      <button
        class="filter-btn"
        class:active={filter === 'CANCELLED'}
        onclick={() => filter = 'CANCELLED'}
      >{$t('goalFilters.archived')}</button>
      <button
        class="filter-btn"
        class:active={filter === 'FAILED'}
        onclick={() => filter = 'FAILED'}
      >{$t('goalFilters.failed')}</button>
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
      gap: var(--s3);
      align-items: flex-start;
      padding: var(--s3) var(--s3);
      width: 100%;
      max-width: 100%;
      box-sizing: border-box;
      overflow: hidden;
    }
    .search-box input {
      width: 100%;
      min-width: 0;
    }
    .search-box {
      flex: 1;
      width: 100%;
      max-width: 100%;
      box-sizing: border-box;
    }
    .editor-controls {
      width: 100%;
      max-width: 100%;
      box-sizing: border-box;
      flex-direction: column;
      align-items: stretch;
      gap: var(--s2_5);
      overflow: hidden;
    }
    .filter-buttons {
      flex-wrap: wrap;
      gap: var(--s1);
    }
    .filter-btn {
      padding: var(--s2) var(--s2_5);
      font-size: 11px;
    }
  }
</style>
