<script lang="ts">
  import GoalCard from './GoalCard.svelte';
  import EmptyState from './EmptyState.svelte';
  import type { Goal, Note } from '$lib/api';
  import type { Tag as TagType } from '$lib/api';
  import { setGoalContext } from '$lib/stores/goalContext';

  interface Props {
    goals: Goal[];
    query: string;
    filter: string | null;
    pinned: Set<number>;
    tags: TagType[];
    notes: Note[];
    getGoalColor: (goal: Goal) => string;
    TEMPORALITY_LABELS: Record<string, string>;
    STATE_LABELS: Record<string, string>;
    formatFailConfig: (config: string) => string;
    onTogglePin: (id: number) => void;
    onClick: (goal: Goal) => void;
    onComplete?: (id: number) => void;
    onFail?: (id: number) => void;
    onDelete?: (id: number) => void;
    onArchive?: (id: number) => void;
  }

  let {
    goals,
    query,
    filter,
    pinned,
    tags,
    notes,
    getGoalColor,
    TEMPORALITY_LABELS,
    STATE_LABELS,
    formatFailConfig,
    onTogglePin,
    onClick,
    onComplete,
    onFail,
    onDelete,
    onArchive,
  }: Props = $props();

  // Set the shared context once so GoalCard can consume tags, notes, callbacks,
  // and label maps without each intermediate level re-forwarding them as props (#351).
  setGoalContext({
    tags,
    notes,
    getGoalColor,
    TEMPORALITY_LABELS,
    STATE_LABELS,
    formatFailConfig,
    onTogglePin,
    onClick,
    onComplete,
    onFail,
    onDelete,
    onArchive,
  });

  function filteredGoals(goals: Goal[], query: string, filter: string | null, pinned: Set<number>) {
    let result = goals;
    if (query) {
      const q = query.toLowerCase();
      result = result.filter(g =>
        g.title.toLowerCase().includes(q) ||
        (g.description && g.description.toLowerCase().includes(q))
      );
    }
    if (filter) {
      if (filter === 'COMPLETED') {
        result = result.filter(g => g.state === 'COMPLETED' || g.is_completed);
      } else if (filter === 'PINNED') {
        result = result.filter(g => pinned.has(g.id));
      } else {
        result = result.filter(g => g.state === filter);
      }
    } else {
      // "Todos" filter (filter === null) excludes archived/cancelled goals
      result = result.filter(g => g.state !== 'CANCELLED');
    }
    return [...result].sort((a, b) => {
      const aPinned = pinned.has(a.id) ? 0 : 1;
      const bPinned = pinned.has(b.id) ? 0 : 1;
      return aPinned - bPinned;
    });
  }

  let visibleGoals = $derived(filteredGoals(goals, query, filter, pinned));
</script>

<div class="editor-grid-container">
  {#if visibleGoals.length === 0}
    <EmptyState message="No hay objetivos que coincidan con los filtros." />
  {:else}
    <div class="editor-grid">
      {#each visibleGoals as goal (goal.id)}
        <GoalCard
          {goal}
          pinned={pinned.has(goal.id)}
        />
      {/each}
    </div>
  {/if}
</div>

<style>
  .editor-grid-container {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
  }

  .editor-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 20px;
    width: 100%;
  }

  @media (max-width: 768px) {
    .editor-grid {
      grid-template-columns: 1fr;
    }
    .editor-grid-container {
      padding: var(--s3);
    }
  }

  @media (max-width: 480px) {
    .editor-grid {
      grid-template-columns: 1fr;
      gap: var(--s3);
    }
  }
</style>
