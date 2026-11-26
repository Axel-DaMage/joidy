<script lang="ts">
  import Inbox from 'lucide-svelte/icons/inbox';
  import Sun from 'lucide-svelte/icons/sun';
  import Moon from 'lucide-svelte/icons/moon';
  import Zap from 'lucide-svelte/icons/zap';
  import Trash2 from 'lucide-svelte/icons/trash-2';
  import ListPlus from 'lucide-svelte/icons/list-plus';
  import { t } from 'svelte-i18n';
  import { api, type Goal, type GoalContext } from '$lib/api';
  import {
    GOAL_CONTEXTS,
    INBOX_PRIORITIES,
    inboxGoals,
    suggestedInboxPriority,
    triagePayload,
    type InboxPriority,
  } from '$lib/utils/goalTriage';
  import { logger } from '$lib/utils/logger';
  import { showNotification } from '$lib/stores/notifications';
  import EmptyState from './EmptyState.svelte';

  interface Props {
    goals: Goal[];
    onOpen?: (goal: Goal) => void;
    getGoalColor?: (goal: Goal) => string;
  }

  let { goals = $bindable(), onOpen, getGoalColor = () => 'var(--accent)' }: Props = $props();

  let items = $derived(inboxGoals(goals));

  const CONTEXT_ICONS: Record<GoalContext, typeof Zap> = {
    ANY: Zap,
    MORNING: Sun,
    NIGHT: Moon,
  };
  const CONTEXT_KEYS: Record<GoalContext, string> = {
    ANY: 'contextAny',
    MORNING: 'contextMorning',
    NIGHT: 'contextNight',
  };
  const CONTEXT_HINTS: Record<GoalContext, string> = {
    ANY: 'contextAnyHint',
    MORNING: 'contextMorningHint',
    NIGHT: 'contextNightHint',
  };

  // Per-goal triage selection. Unset entries fall back to the goal's stored
  // values — state is only written from event handlers, never during render.
  let triage = $state<Record<number, { context: GoalContext; priority: InboxPriority }>>({});
  let busyIds = $state<Set<number>>(new Set());
  let discardConfirmId = $state<number | null>(null);

  function triageFor(goal: Goal) {
    return (
      triage[goal.id] ?? {
        context: goal.context ?? 'ANY',
        priority: suggestedInboxPriority(goal.priority),
      }
    );
  }

  function setContext(goalId: number, context: GoalContext) {
    const current = triage[goalId] ?? {
      context: 'ANY' as GoalContext,
      priority: 'P1' as InboxPriority,
    };
    triage = { ...triage, [goalId]: { ...current, context } };
  }

  function setPriority(goalId: number, priority: InboxPriority) {
    const current = triage[goalId] ?? {
      context: 'ANY' as GoalContext,
      priority: 'P1' as InboxPriority,
    };
    triage = { ...triage, [goalId]: { ...current, priority } };
  }

  function setBusy(goalId: number, busy: boolean) {
    const next = new Set(busyIds);
    if (busy) next.add(goalId);
    else next.delete(goalId);
    busyIds = next;
  }

  async function sendToQueue(goal: Goal) {
    if (busyIds.has(goal.id)) return;
    const sel = triageFor(goal);
    setBusy(goal.id, true);
    try {
      const updated = await api.goals.update(goal.id, triagePayload(sel.context, sel.priority));
      goals = goals.map((g) => (g.id === goal.id ? updated : g));
    } catch (e) {
      logger.error('[GoalInbox] sendToQueue failed:', e);
      showNotification($t('goalsPage.inboxTriageError'), 'error');
    } finally {
      setBusy(goal.id, false);
    }
  }

  async function discardGoal(goal: Goal) {
    // Two-step inline confirm, same pattern as GoalEditor's delete button.
    if (discardConfirmId !== goal.id) {
      discardConfirmId = goal.id;
      setTimeout(() => {
        if (discardConfirmId === goal.id) discardConfirmId = null;
      }, 3000);
      return;
    }
    discardConfirmId = null;
    setBusy(goal.id, true);
    try {
      await api.goals.delete(goal.id);
      goals = goals.filter((g) => g.id !== goal.id);
    } catch (e) {
      logger.error('[GoalInbox] discard failed:', e);
      showNotification($t('goalsPage.inboxDiscardError'), 'error');
    } finally {
      setBusy(goal.id, false);
    }
  }
</script>

<div class="inbox-section">
  <div class="inbox-topbar">
    <div class="inbox-heading">
      <div class="inbox-icon">
        <Inbox size={15} />
      </div>
      <div class="inbox-heading-copy">
        <div class="inbox-title-row">
          <h3 class="inbox-title">{$t('goalsPage.inboxTitle')}</h3>
          {#if items.length > 0}
            <span class="inbox-count">{items.length}</span>
          {/if}
        </div>
      </div>
    </div>
  </div>

  {#if items.length === 0}
    <div class="inbox-empty-wrap">
      <EmptyState title={$t('goalsPage.inboxEmpty')} message={$t('goalsPage.inboxEmptyHint')}>
        {#snippet icon()}
          <Inbox size={36} />
        {/snippet}
      </EmptyState>
    </div>
  {:else}
    <div class="inbox-list">
      <div class="inbox-column-head" aria-hidden="true">
        <span></span>
        <span>{$t('goalsPage.contextLabel')}</span>
        <span>{$t('goalsPage.priority')}</span>
        <span></span>
      </div>
      {#each items as goal (goal.id)}
        {@const sel = triageFor(goal)}
        <div
          class="inbox-card"
          class:busy={busyIds.has(goal.id)}
          style="--goal-color: {getGoalColor(goal)}"
        >
          <div class="inbox-card-main">
            <button
              type="button"
              class="inbox-card-title"
              onclick={() => onOpen?.(goal)}
              title={goal.title}
              >{goal.title}</button
            >
            {#if goal.description}
              <span class="inbox-card-desc">{goal.description.substring(0, 110)}</span>
            {/if}
            <span class="inbox-card-date"
              >{$t('goalCard.created', { values: { date: goal.created_at.split('T')[0] } })}</span
            >
          </div>

          <div class="triage-control context-control">
            <span class="control-label">{$t('goalsPage.contextLabel')}</span>
            <div class="triage-group" role="group" aria-label={$t('goalsPage.contextLabel')}>
              {#each GOAL_CONTEXTS as ctx (ctx)}
                {@const CtxIcon = CONTEXT_ICONS[ctx]}
                <button
                  type="button"
                  class="triage-chip"
                  class:active={sel.context === ctx}
                  onclick={() => setContext(goal.id, ctx)}
                  title={$t(`goalsPage.${CONTEXT_HINTS[ctx]}`)}
                  aria-pressed={sel.context === ctx}
                >
                  <CtxIcon size={12} />
                  <span>{$t(`goalsPage.${CONTEXT_KEYS[ctx]}`)}</span>
                </button>
              {/each}
            </div>
          </div>

          <div class="triage-control priority-control">
            <span class="control-label">{$t('goalsPage.priority')}</span>
            <div class="triage-group priority-group" role="group" aria-label={$t('goalsPage.priority')}>
              {#each INBOX_PRIORITIES as p (p)}
                <button
                  type="button"
                  class="triage-chip prio-chip"
                  class:active={sel.priority === p}
                  onclick={() => setPriority(goal.id, p)}
                  aria-pressed={sel.priority === p}>{p}</button
                >
              {/each}
            </div>
          </div>

          <div class="triage-actions">
            <button
              type="button"
              class="queue-btn"
              onclick={() => sendToQueue(goal)}
              disabled={busyIds.has(goal.id)}
            >
              <ListPlus size={13} />
              <span>{$t('goalsPage.toQueue')}</span>
            </button>
            <button
              type="button"
              class="discard-btn"
              class:confirming={discardConfirmId === goal.id}
              onclick={() => discardGoal(goal)}
              disabled={busyIds.has(goal.id)}
              title={$t('goalsPage.discard')}
              aria-label={$t('goalsPage.discard')}
            >
              <Trash2 size={13} />
              {#if discardConfirmId === goal.id}
                <span>{$t('goalsPage.discardConfirm')}</span>
              {/if}
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .inbox-section {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    min-height: 0;
    margin: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
  }

  .inbox-topbar {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 16px;
    min-height: 48px;
    box-sizing: border-box;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-light);
    background: color-mix(in srgb, var(--surface-hover) 36%, transparent);
    flex-shrink: 0;
  }

  .inbox-heading {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .inbox-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    flex-shrink: 0;
    border-radius: 8px;
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 11%, transparent);
    border: 1px solid color-mix(in srgb, var(--accent) 25%, transparent);
    box-shadow: 0 0 12px color-mix(in srgb, var(--accent) 8%, transparent);
  }

  .inbox-heading-copy {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .inbox-title-row {
    display: flex;
    align-items: center;
    gap: 7px;
    color: var(--text-primary);
  }

  .inbox-title {
    margin: 0;
    font-size: 14px;
    font-weight: 650;
    line-height: 1.2;
  }

  .inbox-count {
    min-width: 20px;
    padding: 1px 7px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 15%, var(--surface));
    border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent);
    color: var(--accent);
    font-size: 10px;
    font-weight: 700;
    text-align: center;
    font-family: var(--font-mono);
  }

  .inbox-list {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px 12px;
    background: color-mix(in srgb, var(--bg) 28%, transparent);
  }

  .inbox-empty-wrap {
    flex: 1;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .inbox-card {
    display: grid;
    grid-template-columns: minmax(250px, 1.2fr) minmax(250px, 0.85fr) minmax(118px, 0.35fr) auto;
    align-items: center;
    gap: 14px;
    padding: 10px 12px;
    background:
      linear-gradient(90deg, color-mix(in srgb, var(--goal-color) 7%, transparent), transparent 34%),
      var(--surface);
    border: 1px solid color-mix(in srgb, var(--goal-color) 20%, var(--border));
    border-left: 3px solid var(--goal-color);
    border-radius: var(--r, 10px);
    transition:
      border-color var(--t-fast, 0.15s ease),
      transform var(--t-fast, 0.15s ease),
      box-shadow var(--t-fast, 0.15s ease);
  }

  .inbox-card:hover {
    border-color: color-mix(in srgb, var(--goal-color) 45%, var(--border));
    transform: translateY(-1px);
    box-shadow: 0 4px 14px color-mix(in srgb, var(--goal-color) 7%, transparent);
  }

  .inbox-card.busy {
    opacity: 0.55;
    pointer-events: none;
  }

  .inbox-card-title:focus-visible,
  .triage-chip:focus-visible,
  .queue-btn:focus-visible,
  .discard-btn:focus-visible {
    outline: 1px solid var(--xp);
    outline-offset: 2px;
  }

  .inbox-card-main {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }

  .inbox-card-title {
    background: none;
    border: none;
    padding: 0;
    font-size: 13px;
    font-weight: 650;
    color: var(--text-primary);
    text-align: left;
    cursor: pointer;
    font-family: var(--font-sans);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .inbox-card-title:hover {
    color: var(--goal-color);
  }

  .inbox-card-desc {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .inbox-card-date {
    font-size: 10px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .triage-control {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }

  .control-label {
    display: none;
    font-size: 9px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-family: var(--font-mono);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .inbox-column-head {
    display: grid;
    grid-template-columns: minmax(250px, 1.2fr) minmax(250px, 0.85fr) minmax(118px, 0.35fr) 123px;
    gap: 14px;
    box-sizing: border-box;
    padding: 0 13px;
    color: var(--text-muted);
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-family: var(--font-mono);
    white-space: nowrap;
  }

  .triage-group {
    display: flex;
    align-items: center;
    gap: 2px;
    height: 30px;
    box-sizing: border-box;
    padding: 2px;
    background: color-mix(in srgb, var(--surface-hover) 58%, transparent);
    border: 1px solid var(--border);
    border-radius: 8px;
    width: fit-content;
    max-width: 100%;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .triage-group::-webkit-scrollbar {
    display: none;
  }

  .triage-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    height: 24px;
    box-sizing: border-box;
    padding: 0 8px;
    border: 1px solid transparent;
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted);
    font-size: 11px;
    line-height: 1;
    font-family: var(--font-sans);
    cursor: pointer;
    transition:
      color var(--t-fast, 0.15s ease),
      background var(--t-fast, 0.15s ease),
      border-color var(--t-fast, 0.15s ease);
    white-space: nowrap;
    flex: 0 0 auto;
  }

  .triage-chip:hover {
    color: var(--text-primary);
    background: color-mix(in srgb, var(--text-primary) 5%, transparent);
  }

  .triage-chip.active {
    background: color-mix(in srgb, var(--goal-color, var(--accent)) 15%, var(--surface));
    border-color: color-mix(in srgb, var(--goal-color, var(--accent)) 38%, transparent);
    color: var(--goal-color, var(--accent));
    font-weight: 650;
  }

  .prio-chip {
    min-width: 34px;
    font-family: var(--font-mono);
    font-weight: 650;
  }

  .triage-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 6px;
    align-self: end;
  }

  .queue-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    height: 30px;
    box-sizing: border-box;
    padding: 0 11px;
    border: 1px solid color-mix(in srgb, var(--accent) 42%, transparent);
    border-radius: 8px;
    background: color-mix(in srgb, var(--accent) 16%, var(--surface));
    color: var(--accent);
    font-size: 11px;
    font-weight: 650;
    font-family: var(--font-sans);
    cursor: pointer;
    transition:
      background var(--t-fast, 0.15s ease),
      border-color var(--t-fast, 0.15s ease),
      transform var(--t-fast, 0.15s ease);
    white-space: nowrap;
  }

  .queue-btn:hover:not(:disabled) {
    background: color-mix(in srgb, var(--accent) 22%, var(--surface));
    border-color: color-mix(in srgb, var(--accent) 58%, transparent);
    transform: translateY(-1px);
  }

  .queue-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .discard-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    width: 30px;
    height: 30px;
    box-sizing: border-box;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: transparent;
    color: var(--text-muted);
    font-size: 10px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast, 0.15s ease);
  }

  .discard-btn:hover:not(:disabled) {
    color: var(--error, #ef4444);
    border-color: color-mix(in srgb, var(--error, #ef4444) 55%, transparent);
    background: color-mix(in srgb, var(--error, #ef4444) 8%, transparent);
  }

  .discard-btn.confirming {
    width: auto;
    padding: 0 8px;
    background: var(--error, #ef4444);
    border-color: var(--error, #ef4444);
    color: #fff;
    font-weight: 650;
  }

  @media (max-width: 1180px) {
    .inbox-column-head {
      display: none;
    }

    .control-label {
      display: block;
    }

    .inbox-card {
      grid-template-columns: minmax(220px, 1fr) auto auto;
    }

    .inbox-card-main {
      grid-column: 1 / -1;
    }

    .context-control {
      grid-column: 1;
    }

    .priority-control {
      grid-column: 2;
    }

    .triage-actions {
      grid-column: 3;
    }
  }

  @media (max-width: 900px) {
    .inbox-card {
      grid-template-columns: minmax(0, 1fr);
      gap: 10px;
    }

    .priority-control,
    .triage-actions {
      grid-column: auto;
      grid-row: auto;
    }

    .triage-actions {
      justify-content: flex-start;
      align-self: auto;
    }
  }

  @media (max-width: 640px) {
    .inbox-topbar {
      align-items: flex-start;
      min-height: 0;
    }

    .inbox-list {
      padding: 8px;
    }

    .triage-group {
      width: 100%;
    }

    .triage-chip {
      flex: 1 0 auto;
    }

    .triage-actions {
      justify-content: stretch;
    }

    .queue-btn {
      flex: 1;
    }
  }
</style>
