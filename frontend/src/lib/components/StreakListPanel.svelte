<script lang="ts">
  import { Plus, Archive, Search, Flame } from 'lucide-svelte';
  import StreakListItem from './StreakListItem.svelte';
  import type { PersonalStreak } from '$lib/api';

  interface Props {
    streaks: PersonalStreak[];
    filteredStreaks: PersonalStreak[];
    loading: boolean;
    error: string;
    selectedId: number | null;
    searchQuery: string;
    showArchived: boolean;
    doneCount: number;
    streakLabel: (n: number) => string;
    freqLabel: (s: PersonalStreak) => string;
    isStreakCompleted: (s: PersonalStreak) => boolean;
    getDaysForCompletion: (s: PersonalStreak) => string;
    onToggleArchive: () => void;
    onCreate: () => void;
    onSelect: (id: number) => void;
    onEdit: (streak: PersonalStreak) => void;
    onDelete: (id: number) => void;
  }

  let {
    streaks,
    filteredStreaks,
    loading,
    error,
    selectedId,
    searchQuery = $bindable(''),
    showArchived = $bindable(false),
    doneCount,
    streakLabel,
    freqLabel,
    isStreakCompleted,
    getDaysForCompletion,
    onToggleArchive,
    onCreate,
    onSelect,
    onEdit,
    onDelete,
  }: Props = $props();
</script>

<div class="list-panel">
  <div class="list-header">
    <div class="list-header-top">
      <div>
        <h1 class="list-title">Rachas</h1>
        <span class="list-sub mono">
          {#if loading}cargando...
          {:else if showArchived}{filteredStreaks.length} archivadas
          {:else}{doneCount}/{filteredStreaks.length} hoy
          {/if}
        </span>
      </div>
      <div class="header-actions">
        <button
          class="header-action-btn"
          class:active={showArchived}
          on:click={onToggleArchive}
          title={showArchived ? 'Volver a activas' : 'Ver archivadas'}
        >
          <Archive size={13} />
        </button>
        <button class="new-btn" on:click={onCreate}>
          <Plus size={13} />
        </button>
      </div>
    </div>

    <div class="search-row">
      <Search size={12} />
      <input
        class="search-input"
        bind:value={searchQuery}
        placeholder="Buscar racha..."
      />
    </div>
  </div>

  <div class="list-body">
    {#if error}
      <div class="error-msg">{error}</div>
    {:else if loading}
      <div class="empty-state mono">Cargando...</div>
    {:else if filteredStreaks.length === 0}
      <div class="empty-state">
        <Flame size={24} style="opacity:.25; margin-bottom:8px;" />
        <p>No hay rachas. ¡Crea una para comenzar!</p>
        <button class="link-btn" on:click={onCreate}>Crear una nueva</button>
      </div>
    {:else}
      {#each filteredStreaks as streak (streak.id)}
        <StreakListItem
          {streak}
          selected={selectedId === streak.id}
          {streakLabel}
          {freqLabel}
          {isStreakCompleted}
          {getDaysForCompletion}
          on:select={(e) => onSelect(e.detail)}
          on:edit={(e) => onEdit(e.detail)}
          on:delete={(e) => onDelete(e.detail)}
        />
      {/each}
    {/if}
  </div>
</div>

<style>
  .list-panel {
    display: flex; flex-direction: column;
    height: 100%;
  }

  .list-header {
    padding: 20px 16px 12px;
    display: flex; flex-direction: column; gap: 10px;
    border-bottom: 1px solid var(--border-light);
    flex-shrink: 0;
  }

  .list-header-top {
    display: flex; align-items: flex-start; justify-content: space-between;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .list-title {
    font-size: 20px; font-weight: 700; color: var(--text-primary);
    letter-spacing: -0.02em;
  }
  .list-sub { font-size: 11px; color: var(--text-muted); }

  .new-btn {
    width: 32px; height: 32px;
    display: flex; align-items: center; justify-content: center;
    background: var(--xp); color: var(--xp-contrast-text, var(--bg));
    border: 1px solid var(--xp); border-radius: 8px;
    cursor: pointer;
  }
  .new-btn:hover { opacity: 0.85; transform: scale(1.05); }

  .header-action-btn {
    width: 32px; height: 32px;
    display: flex; align-items: center; justify-content: center;
    background: var(--surface); color: var(--text-primary);
    border: 1px solid var(--border); border-radius: 8px;
    cursor: pointer; transition: all 0.15s;
  }
  .header-action-btn:hover { background: var(--elevated); border-color: var(--text-muted); transform: scale(1.05); }
  .header-action-btn.active { background: var(--elevated); border-color: var(--text-muted); }

  .search-row {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 10px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text-muted);
    transition: border-color 0.15s;
  }
  .search-row:focus-within { border-color: var(--text-muted); }

  .search-input {
    flex: 1; background: none; border: none; outline: none;
    color: var(--text-primary); font-size: 12px;
  }

  .list-body {
    flex: 1; overflow: hidden; padding: 8px;
    display: flex; flex-direction: column; gap: 4px;
  }
</style>
