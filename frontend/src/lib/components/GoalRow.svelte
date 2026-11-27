<script lang="ts">
  // GoalRow — dense single-line goal item for the editor tab (#goal-redesign).
  // Replaces the old centered GoalCard widget: one row per goal with identity,
  // state, operational meta, inline progress and quick actions. The whole row
  // opens the goal editor; management actions stay available on hover.
  import Pin from 'lucide-svelte/icons/pin';
  import Target from 'lucide-svelte/icons/target';
  import Tag from 'lucide-svelte/icons/tag';
  import FileText from 'lucide-svelte/icons/file-text';
  import CheckCircle2 from 'lucide-svelte/icons/check-circle-2';
  import XCircle from 'lucide-svelte/icons/x-circle';
  import Trash2 from 'lucide-svelte/icons/trash-2';
  import Archive from 'lucide-svelte/icons/archive';
  import ArchiveRestore from 'lucide-svelte/icons/archive-restore';
  import ChevronRight from 'lucide-svelte/icons/chevron-right';
  import Sun from 'lucide-svelte/icons/sun';
  import Moon from 'lucide-svelte/icons/moon';
  import StreakIcon from './StreakIcon.svelte';
  import ProgressBar from './ProgressBar.svelte';
  import { getGoalContext } from '$lib/stores/goalContext';
  import type { Goal, GoalContext } from '$lib/api';
  import { t } from 'svelte-i18n';

  interface Props {
    goal: Goal;
    pinned?: boolean;
    /** Last-opened goal in the editor — persists the selection highlight
     *  across reloads (#1673). */
    selected?: boolean;
  }

  let { goal, pinned = false, selected = false }: Props = $props();

  // Shared context set once by GoalList (#351). Accessed via ctx.* so the
  // getters stay reactive; falls back to no-op defaults outside a provider.
  const ctx = getGoalContext() ?? {
    tags: [] as any[],
    notes: [] as any[],
    getGoalColor: (_g: Goal) => '#c8a96e',
    TEMPORALITY_LABELS: {} as Record<string, string>,
    STATE_LABELS: {} as Record<string, string>,
    formatFailConfig: (_c: string) => '',
    onTogglePin: (_id: number) => {},
    onClick: (_g: Goal) => {},
    onComplete: undefined,
    onFail: undefined,
    onDelete: undefined,
    onArchive: undefined,
  };

  const tagsMap = new Map(ctx.tags.map((tg) => [tg.id, tg]));
  const notesMap = new Map(ctx.notes.map((n) => [n.id, n]));

  let isDone = $derived(goal.state === 'COMPLETED' || goal.is_completed);
  // Effective state for the chip: an ACTIVE goal flagged is_completed reads
  // as completed everywhere else in the UI.
  let resolvedState = $derived(isDone && goal.state !== 'CANCELLED' ? 'COMPLETED' : goal.state);
  let showStateChip = $derived(resolvedState !== 'ACTIVE');
  let goalColor = $derived(ctx.getGoalColor(goal));

  let progressPct = $derived(isDone ? 100 : goal.progress_pct);
  let progressText = $derived.by(() => {
    if (goal.measurement_type === 'PERCENT') {
      return isDone ? '100%' : `${goal.current_value}%`;
    }
    if (isDone) return `${goal.target_value}/${goal.target_value}`;
    return `${goal.current_value}/${goal.target_value}`;
  });

  let linkedLabel = $derived.by(() => {
    if (goal.tag_id) return tagsMap.get(goal.tag_id)?.name ?? '';
    if (goal.note_id) return notesMap.get(goal.note_id)?.title ?? '';
    return '';
  });

  const CONTEXT_META: Partial<Record<GoalContext, { icon: typeof Sun; key: string }>> = {
    MORNING: { icon: Sun, key: 'contextMorning' },
    NIGHT: { icon: Moon, key: 'contextNight' },
  };
  let contextMeta = $derived(CONTEXT_META[goal.context ?? 'ANY']);

  // Action visibility mirrors the today dashboard: complete is offered for
  // goals that can still be decided; archive/fail hide on terminal states.
  let canComplete = $derived(goal.state === 'ACTIVE' || goal.state === 'FAILED');
  let canFail = $derived(
    goal.state === 'ACTIVE' || goal.state === 'PAUSED' || goal.state === 'FAILED'
  );
  let canArchive = $derived(goal.state !== 'COMPLETED' && !isDone);
</script>

<div
  class="grow"
  class:completed={isDone}
  class:failed={goal.state === 'FAILED'}
  class:paused={goal.state === 'PAUSED'}
  class:archived={goal.state === 'CANCELLED'}
  class:selected
  style="--goal-color: {goalColor}"
>
  <button
    class="grow-main"
    onclick={() => ctx.onClick(goal)}
    aria-label={$t('goalCard.openGoal', { values: { title: goal.title } })}
    title={goal.title}
  >
    <span class="grow-icon" aria-hidden="true">
      {#if goal.fail_emoji}
        <StreakIcon name={goal.fail_emoji} size={18} color={goalColor} />
      {:else}
        <Target size={17} color={goalColor} />
      {/if}
    </span>

    <span class="grow-body">
      <span class="grow-title-row">
        {#if pinned}
          <Pin size={11} color="var(--accent)" aria-hidden="true" />
        {/if}
        <span class="grow-title">{goal.title}</span>
        {#if showStateChip}
          <span
            class="grow-state"
            class:completed={resolvedState === 'COMPLETED'}
            class:failed={resolvedState === 'FAILED'}
            class:paused={resolvedState === 'PAUSED'}
            class:archived={resolvedState === 'CANCELLED'}
            >{ctx.STATE_LABELS[resolvedState] || resolvedState}</span
          >
        {/if}
      </span>
      <span class="grow-meta">
        <span class="gm-chip gm-temp"
          >{ctx.TEMPORALITY_LABELS[goal.temporality] || goal.temporality}</span
        >
        {#if goal.priority > 0}
          <span class="gm-chip gm-prio" title="P{goal.priority}">P{goal.priority}</span>
        {/if}
        {#if contextMeta}
          {@const CtxIcon = contextMeta.icon}
          <span
            class="gm-chip gm-ctx"
            title="{$t(`goalsPage.${contextMeta.key}`)} — {$t(`goalsPage.${contextMeta.key}Hint`)}"
            ><CtxIcon size={10} /></span
          >
        {/if}
        {#if linkedLabel}
          <span class="gm-chip gm-link" title={linkedLabel}>
            {#if goal.tag_id}<Tag size={11} />{:else}<FileText size={11} />{/if}
          </span>
        {/if}
        {#if goal.fail_config !== 'STATIC'}
          <span class="gm-chip gm-fail">{ctx.formatFailConfig(goal.fail_config)}</span>
        {/if}
      </span>
    </span>
  </button>

  <div class="grow-side">
    <span class="grow-progress">
      <span class="grow-pct mono">{progressText}</span>
      <ProgressBar value={progressPct} color="var(--goal-color)" height={4} />
    </span>
    <span class="grow-chevron" aria-hidden="true"><ChevronRight size={14} /></span>
  </div>

  <div class="grow-actions">
    {#if ctx.onComplete && canComplete}
      <button
        class="grow-act grow-complete"
        onclick={(e) => {
          e.stopPropagation();
          ctx.onComplete?.(goal.id);
        }}
        title={isDone ? $t('goalCard.markPending') : $t('goalCard.complete')}
        aria-label={isDone ? $t('goalCard.markPending') : $t('goalCard.complete')}
      >
        <CheckCircle2 size={15} />
      </button>
    {/if}

    <span class="grow-secondary">
      {#if ctx.onFail && canFail}
        <button
          class="grow-act grow-fail"
          class:failed={goal.state === 'FAILED'}
          onclick={(e) => {
            e.stopPropagation();
            ctx.onFail?.(goal.id);
          }}
          title={goal.state === 'FAILED' ? $t('goalCard.unfail') : $t('goalCard.fail')}
          aria-label={goal.state === 'FAILED' ? $t('goalCard.unfail') : $t('goalCard.fail')}
        >
          <XCircle size={15} />
        </button>
      {/if}
      {#if ctx.onArchive && canArchive}
        <button
          class="grow-act grow-archive"
          class:archived={goal.state === 'CANCELLED'}
          onclick={(e) => {
            e.stopPropagation();
            ctx.onArchive?.(goal.id);
          }}
          title={goal.state === 'CANCELLED' ? $t('goalCard.unarchive') : $t('goalCard.archive')}
          aria-label={goal.state === 'CANCELLED'
            ? $t('goalCard.unarchive')
            : $t('goalCard.archive')}
        >
          {#if goal.state === 'CANCELLED'}
            <ArchiveRestore size={15} />
          {:else}
            <Archive size={15} />
          {/if}
        </button>
      {/if}
      {#if ctx.onDelete}
        <button
          class="grow-act grow-delete"
          onclick={(e) => {
            e.stopPropagation();
            ctx.onDelete?.(goal);
          }}
          title={$t('goalCard.delete')}
          aria-label={$t('goalCard.delete')}
        >
          <Trash2 size={15} />
        </button>
      {/if}
      <button
        class="grow-act grow-pin"
        class:pinned
        onclick={(e) => {
          e.stopPropagation();
          ctx.onTogglePin(goal.id);
        }}
        title={pinned ? $t('goalCard.unpin') : $t('goalCard.pin')}
        aria-label={pinned ? $t('goalCard.unpin') : $t('goalCard.pin')}
        aria-pressed={pinned}
      >
        <Pin size={15} />
      </button>
    </span>
  </div>
</div>

<style>
  .grow {
    position: relative;
    display: flex;
    align-items: stretch;
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--goal-color) 12%, transparent) 0%,
      color-mix(in srgb, var(--goal-color) 5%, var(--surface)) 34%,
      var(--surface) 72%
    );
    border: 1px solid color-mix(in srgb, var(--goal-color) 38%, var(--border));
    border-left: 4px solid var(--goal-color);
    border-radius: var(--r);
    overflow: hidden;
    box-shadow:
      inset 0 1px 0 color-mix(in srgb, var(--goal-color) 9%, transparent),
      0 4px 16px color-mix(in srgb, var(--goal-color) 5%, transparent);
    transition:
      transform var(--t-fast),
      border-color var(--t-fast),
      box-shadow var(--t-fast),
      background var(--t-fast);
    min-width: 0;
    /* Rows are direct flex children of .goal-list — without this they shrink
       to fit the container instead of overflowing into its scroll. */
    flex-shrink: 0;
  }

  .grow:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--goal-color) 62%, var(--border));
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--goal-color) 16%, transparent) 0%,
      color-mix(in srgb, var(--goal-color) 7%, var(--surface-hover)) 38%,
      var(--surface-hover) 76%
    );
    box-shadow:
      inset 0 1px 0 color-mix(in srgb, var(--goal-color) 12%, transparent),
      0 8px 24px color-mix(in srgb, var(--goal-color) 13%, transparent);
  }

  /* Last-opened goal — a quiet accent ring, weaker than :hover (#1673). */
  .grow.selected {
    border-color: color-mix(in srgb, var(--goal-color) 72%, var(--border));
    box-shadow:
      inset 0 1px 0 color-mix(in srgb, var(--goal-color) 12%, transparent),
      0 0 0 1px color-mix(in srgb, var(--goal-color) 55%, transparent),
      0 6px 20px color-mix(in srgb, var(--goal-color) 10%, transparent);
  }

  .grow.completed {
    opacity: 0.82;
  }
  .grow.failed {
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--error) 13%, transparent),
      color-mix(in srgb, var(--error) 5%, var(--surface)) 42%,
      var(--surface) 78%
    );
  }
  .grow.paused {
    border-left-style: dashed;
    opacity: 0.72;
  }
  .grow.archived {
    border-left-style: dotted;
    opacity: 0.6;
    filter: grayscale(0.25);
  }

  .grow-main {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: var(--s3);
    padding: var(--s2) var(--s3);
    background: none;
    border: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }

  .grow-icon {
    flex-shrink: 0;
    width: 34px;
    height: 34px;
    border-radius: 8px;
    background: color-mix(in srgb, var(--goal-color) 18%, transparent);
    border: 1px solid color-mix(in srgb, var(--goal-color) 30%, transparent);
    box-shadow: inset 0 0 12px color-mix(in srgb, var(--goal-color) 8%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .grow-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .grow-title-row {
    display: flex;
    align-items: center;
    gap: var(--s2);
    min-width: 0;
  }

  .grow-title {
    flex: 1;
    min-width: 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .grow.completed .grow-title {
    text-decoration: line-through;
    text-decoration-color: color-mix(in srgb, var(--goal-color) 60%, transparent);
  }

  .grow-state {
    flex-shrink: 0;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 2px 7px;
    border-radius: 4px;
    background: var(--surface-hover);
    color: var(--text-muted);
  }
  .grow-state.completed {
    background: color-mix(in srgb, var(--success) 14%, transparent);
    color: var(--success);
  }
  .grow-state.failed {
    background: color-mix(in srgb, var(--error) 14%, transparent);
    color: var(--error);
  }
  .grow-state.paused {
    background: color-mix(in srgb, var(--warning, #f59e0b) 14%, transparent);
    color: var(--warning, #f59e0b);
  }
  .grow-state.archived {
    background: color-mix(in srgb, var(--text-muted) 14%, transparent);
    color: var(--text-muted);
  }

  .grow-meta {
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
  }

  .gm-chip {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    flex-shrink: 0;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    padding: 1px 6px;
    border-radius: 4px;
    background: var(--surface-hover);
    border: 1px solid transparent;
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .gm-temp {
    color: var(--goal-color);
    border-color: color-mix(in srgb, var(--goal-color) 24%, transparent);
    background: color-mix(in srgb, var(--goal-color) 8%, transparent);
  }
  .gm-prio {
    color: var(--goal-color);
    border-color: color-mix(in srgb, var(--goal-color) 42%, transparent);
    background: color-mix(in srgb, var(--goal-color) 10%, transparent);
    font-weight: 700;
  }
  .gm-ctx {
    border-color: color-mix(in srgb, var(--xp) 30%, transparent);
    color: var(--xp);
  }
  .gm-fail {
    border-color: color-mix(in srgb, var(--link) 30%, transparent);
    color: var(--link);
  }
  .gm-link {
    padding: 1px 5px;
  }

  .grow-side {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: var(--s2);
    padding-right: var(--s1);
  }

  .grow-progress {
    display: flex;
    flex-direction: column;
    gap: 4px;
    width: 120px;
  }
  .grow-pct {
    font-size: 11px;
    font-weight: 600;
    color: var(--goal-color);
    text-align: right;
    line-height: 1;
  }
  .grow-progress :global(.progress-track) {
    border-radius: 2px;
  }

  .grow-chevron {
    flex-shrink: 0;
    display: inline-flex;
    color: var(--text-muted);
    opacity: 0.5;
    transition: opacity var(--t-fast);
  }
  .grow:hover .grow-chevron {
    opacity: 1;
    color: var(--text-secondary);
  }

  .grow-actions {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: var(--s1);
    padding: 0 var(--s2) 0 var(--s1);
  }

  .grow-act {
    width: 26px;
    height: 26px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--elevated, var(--surface));
    color: var(--text-secondary);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all var(--t-fast);
    flex-shrink: 0;
  }
  .grow-act:hover {
    background: var(--surface-active);
    color: var(--text-primary);
  }

  .grow-complete {
    color: var(--success, #22c55e);
    border-color: color-mix(in srgb, var(--success, #22c55e) 40%, var(--border));
  }
  .grow-complete:hover {
    background: color-mix(in srgb, var(--success, #22c55e) 15%, transparent);
    border-color: var(--success, #22c55e);
  }

  /* Secondary actions reveal on row hover/focus — layout space is reserved
     so nothing shifts. */
  .grow-secondary {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    opacity: 0;
    pointer-events: none;
    transition: opacity var(--t-fast);
  }
  .grow:hover .grow-secondary,
  .grow:focus-within .grow-secondary {
    opacity: 1;
    pointer-events: auto;
  }

  .grow-fail:hover {
    color: var(--error, #ef4444);
    border-color: var(--error, #ef4444);
  }
  .grow-fail.failed {
    background: var(--error, #ef4444);
    border-color: var(--error, #ef4444);
    color: #fff;
  }
  .grow-archive:hover {
    color: var(--warning, #f59e0b);
    border-color: var(--warning, #f59e0b);
  }
  .grow-archive.archived {
    background: color-mix(in srgb, var(--warning, #f59e0b) 15%, transparent);
    color: var(--warning, #f59e0b);
  }
  .grow-delete:hover {
    color: #ef4444;
    border-color: #ef4444;
  }
  .grow-pin.pinned {
    color: var(--accent);
    border-color: var(--accent);
  }

  @media (max-width: 640px) {
    .grow-progress {
      width: 84px;
    }
    .gm-fail,
    .gm-link {
      display: none;
    }
  }
</style>
