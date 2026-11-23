<script lang="ts">
  // GoalFilters — slim toolbar for the goals editor tab: search, state filter
  // chips and energy-context chips. No page title (the tab already labels the
  // view) and no Inbox state chip (the dedicated Inbox tab owns triage).
  import Search from 'lucide-svelte/icons/search';
  import Sun from 'lucide-svelte/icons/sun';
  import Moon from 'lucide-svelte/icons/moon';
  import Zap from 'lucide-svelte/icons/zap';
  import X from 'lucide-svelte/icons/x';
  import { t } from 'svelte-i18n';
  import type { GoalContext } from '$lib/api';

  interface Props {
    query?: string;
    filter?: string | null;
    contextFilter?: GoalContext | null;
  }

  let {
    query = $bindable(''),
    filter = $bindable<string | null>(null),
    contextFilter = $bindable<GoalContext | null>(null),
  }: Props = $props();

  const STATE_FILTERS = [
    { value: null, key: 'all' },
    { value: 'PINNED', key: 'pinned' },
    { value: 'ACTIVE', key: 'active' },
    { value: 'COMPLETED', key: 'completed' },
    { value: 'CANCELLED', key: 'archived' },
    { value: 'FAILED', key: 'failed' },
  ] as const;

  const CONTEXT_CHIPS: { value: GoalContext; key: string }[] = [
    { value: 'MORNING', key: 'contextMorning' },
    { value: 'NIGHT', key: 'contextNight' },
    { value: 'ANY', key: 'contextAny' },
  ];

  function toggleContext(ctx: GoalContext) {
    contextFilter = contextFilter === ctx ? null : ctx;
  }
</script>

<div class="gf">
  <label class="gf-search">
    <Search size={13} />
    <input
      type="text"
      placeholder={$t('goalFilters.searchPlaceholder')}
      aria-label={$t('goalFilters.searchPlaceholder')}
      bind:value={query}
    />
  </label>

  <div class="gf-group" role="group" aria-label={$t('goalFilters.stateGroup')}>
    {#each STATE_FILTERS as f (f.key)}
      <button
        type="button"
        class="gf-chip"
        class:active={filter === f.value}
        aria-pressed={filter === f.value}
        onclick={() => (filter = f.value)}
      >
        {$t(`goalFilters.${f.key}`)}
      </button>
    {/each}
    {#if filter === 'INBOX'}
      <!-- Persisted legacy value: keep it visible and clearable even though
           the dedicated chip was removed. -->
      <button
        type="button"
        class="gf-chip active"
        title={$t('goalFilters.clearFilter')}
        onclick={() => (filter = null)}
      >
        {$t('goalsPage.inboxTab')}
        <X size={10} />
      </button>
    {/if}
  </div>

  <div class="gf-group gf-ctx" role="group" aria-label={$t('goalsPage.contextLabel')}>
    {#each CONTEXT_CHIPS as chip (chip.value)}
      <button
        type="button"
        class="gf-chip gf-ctx-chip"
        class:active={contextFilter === chip.value}
        onclick={() => toggleContext(chip.value)}
        title={$t(`goalsPage.${chip.key}Hint`)}
        aria-pressed={contextFilter === chip.value}
      >
        {#if chip.value === 'MORNING'}<Sun size={11} />{:else if chip.value === 'NIGHT'}<Moon
            size={11}
          />{:else}<Zap size={11} />{/if}
        {$t(`goalsPage.${chip.key}`)}
      </button>
    {/each}
  </div>
</div>

<style>
  .gf {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: var(--s2);
    flex-wrap: wrap;
  }

  .gf-search {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    background: var(--surface-hover);
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    width: 200px;
    flex-shrink: 0;
  }
  .gf-search:focus-within {
    border-color: var(--xp);
  }
  .gf-search input {
    background: transparent;
    border: none;
    color: var(--text-primary);
    font-size: 12px;
    outline: none;
    width: 100%;
    min-width: 0;
  }
  .gf-search input::placeholder {
    color: var(--text-muted);
  }

  .gf-group {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
    min-width: 0;
  }

  .gf-ctx {
    padding-left: var(--s2);
    border-left: 1px solid var(--border);
  }

  .gf-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 9px;
    border-radius: 6px;
    font-size: 11px;
    font-family: var(--font-sans);
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--t-fast);
    white-space: nowrap;
  }
  .gf-chip:hover {
    background: var(--surface-hover);
    color: var(--text-primary);
  }
  .gf-chip.active {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-contrast-text, var(--bg));
    font-weight: 600;
  }
  .gf-chip:focus-visible {
    outline: 1px solid var(--xp);
    outline-offset: 2px;
  }

  @media (max-width: 640px) {
    .gf {
      flex-direction: column;
      align-items: stretch;
    }
    .gf-search {
      width: 100%;
    }
    .gf-ctx {
      border-left: none;
      padding-left: 0;
    }
  }
</style>
