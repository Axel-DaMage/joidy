<script lang="ts">
  import { Inbox, Sun, Moon, Zap, Trash2, ListPlus } from 'lucide-svelte';
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
  }

  let { goals = $bindable(), onOpen }: Props = $props();

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
  <div class="inbox-header">
    <div class="inbox-title-row">
      <Inbox size={18} />
      <h3 class="inbox-title">{$t('goalsPage.inboxTitle')}</h3>
      {#if items.length > 0}
        <span class="inbox-count">{items.length}</span>
      {/if}
    </div>
    <p class="inbox-subtitle">{$t('goalsPage.inboxHint')}</p>
  </div>

  {#if items.length === 0}
    <EmptyState title={$t('goalsPage.inboxEmpty')} message={$t('goalsPage.inboxEmptyHint')}>
      {#snippet icon()}
        <Inbox size={36} />
      {/snippet}
    </EmptyState>
  {:else}
    <div class="inbox-list">
      {#each items as goal (goal.id)}
        {@const sel = triageFor(goal)}
        <div class="inbox-card" class:busy={busyIds.has(goal.id)}>
          <div class="inbox-card-main">
            <button class="inbox-card-title" onclick={() => onOpen?.(goal)} title={goal.title}
              >{goal.title}</button
            >
            {#if goal.description}
              <span class="inbox-card-desc">{goal.description.substring(0, 80)}</span>
            {/if}
            <span class="inbox-card-date"
              >{$t('goalCard.created', { values: { date: goal.created_at.split('T')[0] } })}</span
            >
          </div>

          <div class="inbox-card-triage">
            <div class="triage-group" role="group" aria-label={$t('goalsPage.contextLabel')}>
              {#each GOAL_CONTEXTS as ctx}
                {@const CtxIcon = CONTEXT_ICONS[ctx]}
                <button
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

            <div class="triage-group" role="group" aria-label={$t('goalsPage.priority')}>
              {#each INBOX_PRIORITIES as p}
                <button
                  class="triage-chip prio-chip"
                  class:active={sel.priority === p}
                  onclick={() => setPriority(goal.id, p)}
                  aria-pressed={sel.priority === p}>{p}</button
                >
              {/each}
            </div>

            <div class="triage-actions">
              <button
                class="queue-btn"
                onclick={() => sendToQueue(goal)}
                disabled={busyIds.has(goal.id)}
              >
                <ListPlus size={13} />
                <span>{$t('goalsPage.toQueue')}</span>
              </button>
              <button
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
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .inbox-section {
    display: flex;
    flex-direction: column;
    gap: var(--s4, 16px);
    max-width: 800px;
    margin: 0 auto;
    width: 100%;
  }

  .inbox-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .inbox-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-primary);
  }

  .inbox-title {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
  }

  .inbox-count {
    min-width: 20px;
    padding: 1px 7px;
    border-radius: 999px;
    background: var(--accent);
    color: var(--accent-contrast-text, var(--bg));
    font-size: 11px;
    font-weight: 600;
    text-align: center;
    font-family: var(--font-mono);
  }

  .inbox-subtitle {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
  }

  .inbox-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .inbox-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 12px 14px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r, 10px);
    transition: border-color var(--t-fast, 0.15s ease);
  }

  .inbox-card:hover {
    border-color: var(--accent);
  }

  .inbox-card.busy {
    opacity: 0.55;
    pointer-events: none;
  }

  .inbox-card-main {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
    flex: 1;
  }

  .inbox-card-title {
    background: none;
    border: none;
    padding: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    text-align: left;
    cursor: pointer;
    font-family: var(--font-sans);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .inbox-card-title:hover {
    color: var(--accent);
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

  .inbox-card-triage {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .triage-group {
    display: flex;
    gap: 4px;
    padding: 3px;
    background: var(--surface-hover);
    border-radius: 8px;
  }

  .triage-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    border: 1px solid transparent;
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted);
    font-size: 11px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast, 0.15s ease);
  }

  .triage-chip:hover {
    color: var(--text-primary);
    background: var(--elevated, var(--surface));
  }

  .triage-chip.active {
    background: var(--accent);
    color: var(--accent-contrast-text, var(--bg));
    font-weight: 600;
  }

  .prio-chip {
    font-family: var(--font-mono);
    font-weight: 600;
  }

  .triage-actions {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .queue-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 6px 12px;
    border: 1px solid var(--accent);
    border-radius: 8px;
    background: var(--accent);
    color: var(--accent-contrast-text, var(--bg));
    font-size: 12px;
    font-weight: 600;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: opacity var(--t-fast, 0.15s ease);
  }

  .queue-btn:hover:not(:disabled) {
    opacity: 0.85;
  }

  .queue-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .discard-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 6px 8px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: transparent;
    color: var(--text-muted);
    font-size: 11px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast, 0.15s ease);
  }

  .discard-btn:hover:not(:disabled) {
    color: var(--error, #ef4444);
    border-color: var(--error, #ef4444);
  }

  .discard-btn.confirming {
    background: var(--error, #ef4444);
    border-color: var(--error, #ef4444);
    color: #fff;
    font-weight: 600;
  }

  @media (max-width: 768px) {
    .inbox-card {
      flex-direction: column;
      align-items: stretch;
      gap: 10px;
    }

    .inbox-card-triage {
      justify-content: flex-start;
    }
  }
</style>
