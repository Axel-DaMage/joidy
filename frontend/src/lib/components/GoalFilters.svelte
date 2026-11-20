<script lang="ts">
  import Search from 'lucide-svelte/icons/search';
  import Sun from 'lucide-svelte/icons/sun';
  import Moon from 'lucide-svelte/icons/moon';
  import Zap from 'lucide-svelte/icons/zap';
  import { t } from 'svelte-i18n';
  import type { GoalContext } from '$lib/api';

  let {
    query = $bindable(''),
    filter = $bindable<string | null>(null),
    contextFilter = $bindable<GoalContext | null>(null)
  } = $props();

  const CONTEXT_CHIPS: { value: GoalContext; key: string }[] = [
    { value: 'MORNING', key: 'contextMorning' },
    { value: 'NIGHT', key: 'contextNight' },
    { value: 'ANY', key: 'contextAny' },
  ];

  function toggleContext(ctx: GoalContext) {
    contextFilter = contextFilter === ctx ? null : ctx;
  }
</script>

<div class="editor-header">
  <h3 class="editor-title">{$t('goalFilters.editorTitle')}</h3>
  <div class="editor-controls">
    <div class="search-box">
      <Search size={16} />
      <input
        type="text"
        placeholder={$t('goalFilters.searchPlaceholder')}
        aria-label={$t('goalFilters.searchPlaceholder')}
        bind:value={query}
      />
    </div>
    <div class="filter-buttons">
      <button
        class="filter-btn"
        class:active={filter === null}
        aria-pressed={filter === null}
        onclick={() => filter = null}
      >{$t('goalFilters.all')}</button>
      <button
        class="filter-btn"
        class:active={filter === 'PINNED'}
        aria-pressed={filter === 'PINNED'}
        onclick={() => filter = 'PINNED'}
      >{$t('goalFilters.pinned')}</button>
      <button
        class="filter-btn"
        class:active={filter === 'ACTIVE'}
        aria-pressed={filter === 'ACTIVE'}
        onclick={() => filter = 'ACTIVE'}
      >{$t('goalFilters.active')}</button>
      <button
        class="filter-btn"
        class:active={filter === 'COMPLETED'}
        aria-pressed={filter === 'COMPLETED'}
        onclick={() => filter = 'COMPLETED'}
      >{$t('goalFilters.completed')}</button>
      <button
        class="filter-btn"
        class:active={filter === 'CANCELLED'}
        aria-pressed={filter === 'CANCELLED'}
        onclick={() => filter = 'CANCELLED'}
      >{$t('goalFilters.archived')}</button>
      <button
        class="filter-btn"
        class:active={filter === 'FAILED'}
        aria-pressed={filter === 'FAILED'}
        onclick={() => filter = 'FAILED'}
      >{$t('goalFilters.failed')}</button>
      <button
        class="filter-btn inbox-filter"
        class:active={filter === 'INBOX'}
        aria-pressed={filter === 'INBOX'}
        onclick={() => filter = 'INBOX'}
      >{$t('goalsPage.inboxTab')}</button>
    </div>
    <div class="context-filter" role="group" aria-label={$t('goalsPage.contextLabel')}>
      {#each CONTEXT_CHIPS as chip}
        <button
          class="filter-btn context-chip"
          class:active={contextFilter === chip.value}
          onclick={() => toggleContext(chip.value)}
          title={$t(`goalsPage.${chip.key}Hint`)}
          aria-pressed={contextFilter === chip.value}
        >
          {#if chip.value === 'MORNING'}<Sun size={11} />{:else if chip.value === 'NIGHT'}<Moon size={11} />{:else}<Zap size={11} />{/if}
          {$t(`goalsPage.${chip.key}`)}
        </button>
      {/each}
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
  .search-box input:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 2px;
    border-radius: var(--r-sm);
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

  .context-filter {
    display: flex;
    gap: 6px;
    align-items: center;
    padding-left: 8px;
    border-left: 1px solid var(--border);
  }

  .context-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
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
    .context-filter {
      border-left: none;
      padding-left: 0;
      flex-wrap: wrap;
    }
    .filter-btn {
      padding: var(--s2) var(--s2_5);
      font-size: 11px;
    }
  }
</style>
