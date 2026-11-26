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
        <span>{$t(`goalsPage.${chip.key}`)}</span>
      </button>
    {/each}
  </div>
</div>

<style>
  .gf {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .gf-search {
    display: flex;
    align-items: center;
    gap: 7px;
    height: 32px;
    padding: 0 11px;
    background: color-mix(in srgb, var(--surface-hover) 78%, transparent);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-muted);
    width: min(240px, 24vw);
    flex: 0 0 auto;
    transition:
      border-color var(--t-fast),
      box-shadow var(--t-fast),
      background var(--t-fast);
  }
  .gf-search:focus-within {
    border-color: color-mix(in srgb, var(--xp) 62%, var(--border));
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--xp) 10%, transparent);
    background: var(--surface);
    color: var(--xp);
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
    gap: 2px;
    height: 32px;
    padding: 2px;
    flex: 0 1 auto;
    min-width: 0;
    overflow-x: auto;
    scrollbar-width: none;
    background: color-mix(in srgb, var(--surface-hover) 56%, transparent);
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .gf-group::-webkit-scrollbar {
    display: none;
  }

  .gf-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    height: 26px;
    padding: 0 9px;
    border-radius: 6px;
    font-size: 11px;
    line-height: 1;
    font-family: var(--font-sans);
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition:
      color var(--t-fast),
      background var(--t-fast),
      border-color var(--t-fast);
    white-space: nowrap;
    flex: 0 0 auto;
  }
  .gf-chip:hover {
    background: color-mix(in srgb, var(--text-primary) 5%, transparent);
    color: var(--text-primary);
  }
  .gf-chip.active {
    background: color-mix(in srgb, var(--accent) 15%, var(--surface));
    border-color: color-mix(in srgb, var(--accent) 38%, transparent);
    color: var(--accent);
    font-weight: 650;
  }
  .gf-chip:focus-visible {
    outline: 1px solid var(--xp);
    outline-offset: 2px;
  }

  .gf-ctx-chip {
    padding-inline: 8px;
  }
  .gf-ctx-chip span {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  @media (max-width: 1100px) {
    .gf {
      flex-wrap: wrap;
    }
    .gf-search {
      flex: 1 1 180px;
      width: auto;
    }
  }

  @media (max-width: 640px) {
    .gf {
      flex-direction: column;
      align-items: stretch;
    }
    .gf-search,
    .gf-group {
      width: 100%;
      flex-basis: auto;
    }
    .gf-chip {
      flex: 1 0 auto;
    }
  }
</style>
