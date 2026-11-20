<script lang="ts">
  import GoalCard from './GoalCard.svelte';
  import EmptyState from './EmptyState.svelte';
  import type { Goal, GoalContext, Note } from '$lib/api';
  import type { Tag as TagType } from '$lib/api';
  import { setGoalContext } from '$lib/stores/goalContext';

  interface Props {
    goals: Goal[];
    query: string;
    filter: string | null;
    contextFilter?: GoalContext | null;
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
    onDelete?: (goal: Goal) => void;
    onArchive?: (id: number) => void;
  }

  let {
    goals,
    query,
    filter,
    contextFilter = null,
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
    get tags() { return tags; },
    get notes() { return notes; },
    get getGoalColor() { return getGoalColor; },
    get TEMPORALITY_LABELS() { return TEMPORALITY_LABELS; },
    get STATE_LABELS() { return STATE_LABELS; },
    get formatFailConfig() { return formatFailConfig; },
    get onTogglePin() { return onTogglePin; },
    get onClick() { return onClick; },
    get onComplete() { return onComplete; },
    get onFail() { return onFail; },
    get onDelete() { return onDelete; },
    get onArchive() { return onArchive; },
  });

  function filteredGoals(
    goals: Goal[],
    query: string,
    filter: string | null,
    contextFilter: GoalContext | null,
    pinned: Set<number>
  ) {
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
        // Pinned view keeps its semantics but still hides raw inbox captures
        result = result.filter(g => pinned.has(g.id) && g.state !== 'INBOX');
      } else {
        result = result.filter(g => g.state === filter);
      }
    } else {
      // "Todos" filter (filter === null) excludes archived/cancelled goals and
      // untriaged inbox captures (#1200 — inbox lives in its own section)
      result = result.filter(g => g.state !== 'CANCELLED' && g.state !== 'INBOX');
    }
    if (contextFilter) {
      result = result.filter(g => (g.context ?? 'ANY') === contextFilter);
    }
    return [...result].sort((a, b) => {
      const aPinned = pinned.has(a.id) ? 0 : 1;
      const bPinned = pinned.has(b.id) ? 0 : 1;
      if (aPinned !== bPinned) return aPinned - bPinned;
      const prio = (b.priority ?? 0) - (a.priority ?? 0);
      if (prio !== 0) return prio;
      return (b.created_at ?? '').localeCompare(a.created_at ?? '');
    });
  }

  let visibleGoals = $derived(filteredGoals(goals, query, filter, contextFilter, pinned));
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
