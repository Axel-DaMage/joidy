<script lang="ts">
  import GoalRow from './GoalRow.svelte';
  import EmptyState from './EmptyState.svelte';
  import Target from 'lucide-svelte/icons/target';
  import type { Goal, GoalContext, Note } from '$lib/api';
  import type { Tag as TagType } from '$lib/api';
  import { setGoalContext } from '$lib/stores/goalContext';
  import { rise, staggerDelay } from '$lib/utils/motion';
  import { t } from 'svelte-i18n';

  interface Props {
    goals: Goal[];
    query: string;
    filter: string | null;
    contextFilter?: GoalContext | null;
    pinned: Set<number>;
    /** Last-opened goal — highlighted so the editor selection survives a
     *  reload (#1673). */
    selectedId?: number | null;
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
    /** Opens the create-goal form — used by the empty state CTA. */
    onNew?: () => void;
  }

  let {
    goals,
    query,
    filter,
    contextFilter = null,
    pinned,
    selectedId = null,
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
    onNew,
  }: Props = $props();

  // Set the shared context once so GoalRow can consume tags, notes, callbacks,
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
  // "No goals at all" gets the create CTA; "filters match nothing" gets a
  // plain message (the toolbar owns clearing them).
  let hasAnyGoal = $derived(goals.length > 0);
</script>

<div class="goal-list">
  {#if visibleGoals.length === 0}
    {#if !hasAnyGoal && onNew}
      <EmptyState
        title={$t('goalsPage.editorEmptyTitle')}
        message={$t('goalsPage.editorEmptyHint')}
        actionLabel={$t('goalsPage.newGoal')}
        onAction={onNew}
      >
        {#snippet icon()}<Target size={36} />{/snippet}
      </EmptyState>
    {:else}
      <EmptyState message={$t('goalsPage.editorNoMatches')} />
    {/if}
  {:else}
    {#each visibleGoals as goal, i (goal.id)}
      <!-- Staggered rise entrance (shared motion system, #1657). The wrapper
           keeps flex-shrink:0 — GoalRow only carries it as a direct child. -->
      <div
        class="goal-item"
        in:rise={{ delay: staggerDelay(i, { step: 30 }), duration: 300 }}
      >
        <GoalRow {goal} pinned={pinned.has(goal.id)} selected={goal.id === selectedId} />
      </div>
    {/each}
  {/if}
</div>

<style>
  .goal-list {
    min-height: 0;
    min-width: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    padding: var(--s1);
  }
  /* Rows are direct flex children of .goal-list — without flex-shrink:0 they
     would squash instead of overflowing into scroll (mirrors .grow in
     GoalRow). */
  .goal-item {
    flex-shrink: 0;
    min-width: 0;
  }
  .goal-list > :global(.empty-state) {
    margin: auto;
  }
</style>
