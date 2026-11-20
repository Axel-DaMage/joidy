<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api, type CalendarTask, type Goal } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import { showNotification } from '$lib/stores/notifications';
  import { applyGamificationResult } from '$lib/stores/gamification';
  import {
    buildExecutionQueue,
    goalQueueKey,
    resolveExecutionContext,
    taskQueueKey,
    type ExecutionItem,
  } from '$lib/utils/executionQueue';
  import { inboxGoals } from '$lib/utils/goalTriage';
  import { running as pomRunning, secondsLeft, toggleTimer } from '$lib/stores/pomodoro';
  import { isActive as focusActive, startFocusMode, stopFocusMode } from '$lib/stores/focusMode';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import SacredCalendar from '$lib/components/SacredCalendar.svelte';
  import Check from 'lucide-svelte/icons/check';
  import Crosshair from 'lucide-svelte/icons/crosshair';
  import Inbox from 'lucide-svelte/icons/inbox';
  import Moon from 'lucide-svelte/icons/moon';
  import Pause from 'lucide-svelte/icons/pause';
  import Sunrise from 'lucide-svelte/icons/sunrise';
  import Target from 'lucide-svelte/icons/target';
  import Timer from 'lucide-svelte/icons/timer';
  import Zap from 'lucide-svelte/icons/zap';
  import { t } from 'svelte-i18n';

  /**
   * «Modo Ejecución» (#1201): single-focus view that merges the goals
   * execution queue with today's calendar-task queue. Freezing rule: nothing
   * can be created here — capture lives in the Inbox.
   */

  // Goal queue items + today's open calendar tasks (execution order, #1234).
  let goalItems = $state<Goal[]>([]);
  let taskItems = $state<CalendarTask[]>([]);
  // Full goals list — only needed for the first-run onboarding condition.
  let allGoals = $state<Goal[]>([]);
  let loading = $state(true);
  let loadError = $state('');
  // "Hazla ahora" local promotion — moves the item into the hero slot without
  // touching backend ordering.
  let promotedKey = $state<string | null>(null);
  let busyKey = $state<string | null>(null);

  // Same rule as the backend's context=auto resolution (#1198): local hour
  // below the cutoff → MORNING, else NIGHT.
  const localContext = resolveExecutionContext(new Date().getHours());

  let queue = $derived(buildExecutionQueue(goalItems, taskItems));
  let heroItem = $derived(queue.find((i) => i.key === promotedKey) ?? queue[0] ?? null);
  let restItems = $derived(heroItem ? queue.filter((i) => i.key !== heroItem.key) : []);

  // First-run onboarding: nothing queued AND the user never triaged a goal to
  // an energy context AND the inbox is empty → explain capture → triage →
  // execute instead of showing a bare empty state.
  let showOnboarding = $derived(
    !loading &&
      queue.length === 0 &&
      !allGoals.some((g) => g.context !== 'ANY') &&
      inboxGoals(allGoals).length === 0
  );

  let pomTime = $derived(
    `${String(Math.floor($secondsLeft / 60)).padStart(2, '0')}:${String($secondsLeft % 60).padStart(
      2,
      '0'
    )}`
  );

  function contextLabel(ctx: Goal['context']): string {
    if (ctx === 'MORNING') return $t('goalsPage.contextMorning');
    if (ctx === 'NIGHT') return $t('goalsPage.contextNight');
    return $t('goalsPage.contextAny');
  }

  function prioLabel(item: ExecutionItem): string {
    if (item.kind === 'goal') return `P${item.goal.priority}`;
    return $t(`executionPage.prio.${item.task.priority.toLowerCase()}`);
  }

  function prioClass(item: ExecutionItem): string {
    if (item.kind === 'goal') return 'prio prio-goal';
    return `prio prio-${item.task.priority.toLowerCase()}`;
  }

  function toggleFocus(): void {
    if ($focusActive) {
      stopFocusMode();
    } else {
      startFocusMode();
    }
  }

  function promote(item: ExecutionItem): void {
    promotedKey = item.key;
  }

  async function refresh(): Promise<void> {
    loadError = '';
    try {
      const [gq, tq, all] = await Promise.all([
        api.goals.executionQueue('auto'),
        api.calendarTasks.executionQueue(),
        api.goals.list(),
      ]);
      goalItems = gq.items;
      taskItems = tq;
      allGoals = all;
      // Drop the promotion if the promoted item left the queue.
      if (promotedKey) {
        const keys = new Set([
          ...gq.items.map((g) => goalQueueKey(g.id)),
          ...tq.map((tk) => taskQueueKey(tk.id)),
        ]);
        if (!keys.has(promotedKey)) promotedKey = null;
      }
    } catch (e) {
      logger.error('[execution] queue fetch failed:', e);
      loadError = $t('executionPage.loadError');
    } finally {
      loading = false;
    }
  }

  async function completeItem(item: ExecutionItem): Promise<void> {
    busyKey = item.key;
    try {
      if (item.kind === 'goal') {
        const result = await api.goals.complete(item.goal.id);
        applyGamificationResult(result.gamification);
      } else {
        await api.calendarTasks.toggleDone(item.task.id);
        showNotification($t('executionPage.taskDone'), 'success');
      }
      if (promotedKey === item.key) promotedKey = null;
      await refresh();
    } catch (e) {
      logger.error('[execution] complete failed:', e);
      showNotification($t('executionPage.completeError'), 'error');
    } finally {
      busyKey = null;
    }
  }

  async function pauseItem(item: ExecutionItem): Promise<void> {
    if (item.kind !== 'goal') return;
    busyKey = item.key;
    try {
      await api.goals.update(item.goal.id, { state: 'PAUSED' });
      if (promotedKey === item.key) promotedKey = null;
      await refresh();
    } catch (e) {
      logger.error('[execution] pause failed:', e);
      showNotification($t('executionPage.pauseError'), 'error');
    } finally {
      busyKey = null;
    }
  }

  onMount(() => {
    void refresh();
  });
</script>

<svelte:head>
  <title>{$t('executionPage.pageTitle')}</title>
</svelte:head>

<div class="execution-page">
  <header class="exec-header">
    <div class="exec-title">
      <h3>{$t('executionPage.title')}</h3>
      <span class="context-badge">
        {#if localContext === 'MORNING'}
          <Sunrise size={12} />
          {$t('executionPage.contextMorning')}
        {:else}
          <Moon size={12} />
          {$t('executionPage.contextNight')}
        {/if}
      </span>
    </div>
    <a class="btn btn-ghost inbox-link" href="/goals?tab=inbox">
      <Inbox size={14} />
      {$t('executionPage.toInbox')}
    </a>
  </header>

  {#if loadError}
    <div class="error-banner">{loadError}</div>
  {/if}

  <div class="exec-layout">
    <div class="exec-main">
      {#if loading}
        <div class="exec-loading caption">{$t('executionPage.loading')}</div>
      {:else if showOnboarding}
        <div class="onboarding card">
          <div class="onboarding-icon"><Target size={36} /></div>
          <h4>{$t('executionPage.onboardingTitle')}</h4>
          <p class="onboarding-hint">{$t('executionPage.onboardingHint')}</p>
          <ol class="steps">
            <li>
              <strong>1 · {$t('executionPage.stepCapture')}</strong>
              <span>{$t('executionPage.stepCaptureHint')}</span>
            </li>
            <li>
              <strong>2 · {$t('executionPage.stepTriage')}</strong>
              <span>{$t('executionPage.stepTriageHint')}</span>
            </li>
            <li>
              <strong>3 · {$t('executionPage.stepExecute')}</strong>
              <span>{$t('executionPage.stepExecuteHint')}</span>
            </li>
          </ol>
          <a class="btn btn-primary" href="/goals?tab=inbox">
            <Inbox size={14} />
            {$t('executionPage.goToInbox')}
          </a>
        </div>
      {:else if !heroItem}
        <EmptyState
          title={$t('executionPage.emptyTitle')}
          message={$t('executionPage.emptyHint')}
          actionLabel={$t('executionPage.goToInbox')}
          onAction={() => goto('/goals?tab=inbox')}
        >
          {#snippet icon()}<Check size={44} />{/snippet}
        </EmptyState>
      {:else}
        <!-- «Siguiente» hero card -->
        <section class="hero card" aria-label={$t('executionPage.next')}>
          <div class="hero-kicker">
            <span class="hero-label">{$t('executionPage.next')}</span>
            <span class="kind-chip">
              {heroItem.kind === 'goal'
                ? $t('executionPage.kindGoal')
                : $t('executionPage.kindTask')}
            </span>
            <span class={prioClass(heroItem)}>{prioLabel(heroItem)}</span>
            {#if heroItem.kind === 'goal' && heroItem.goal.context !== 'ANY'}
              <span class="ctx-chip">{contextLabel(heroItem.goal.context)}</span>
            {/if}
            {#if heroItem.startTime}
              <span class="time-chip mono">{heroItem.startTime}</span>
            {/if}
          </div>

          <h2 class="hero-title">{heroItem.title}</h2>

          {#if heroItem.kind === 'goal' && heroItem.goal.measurement_type === 'COUNT' && heroItem.goal.target_value > 1}
            <div class="hero-progress caption">
              {heroItem.goal.current_value} / {heroItem.goal.target_value} ·
              {Math.round(heroItem.goal.progress_pct)}%
            </div>
          {/if}

          <div class="hero-actions">
            <button
              class="btn btn-primary hero-cta"
              disabled={busyKey === heroItem.key}
              onclick={() => completeItem(heroItem!)}
            >
              <Check size={16} />
              {$t('executionPage.complete')}
            </button>
            {#if heroItem.kind === 'goal'}
              <button
                class="btn"
                disabled={busyKey === heroItem.key}
                onclick={() => pauseItem(heroItem!)}
              >
                <Pause size={14} />
                {$t('executionPage.pause')}
              </button>
            {/if}
            <div class="hero-focus-tools">
              <button
                class="btn btn-ghost"
                class:active={$pomRunning}
                onclick={toggleTimer}
                title={$pomRunning
                  ? $t('executionPage.pausePomodoro')
                  : $t('executionPage.startPomodoro')}
              >
                <Timer size={14} />
                {$pomRunning ? pomTime : $t('executionPage.startPomodoro')}
              </button>
              <button
                class="btn btn-ghost"
                class:active={$focusActive}
                onclick={toggleFocus}
                title={$focusActive
                  ? $t('executionPage.stopFocus')
                  : $t('executionPage.startFocus')}
              >
                <Crosshair size={14} />
                {$focusActive ? $t('executionPage.stopFocus') : $t('executionPage.startFocus')}
              </button>
            </div>
          </div>
        </section>

        {#if restItems.length > 0}
          <section class="queue">
            <h5 class="queue-title">{$t('executionPage.queueTitle')}</h5>
            <ul class="queue-list">
              {#each restItems as item, i (item.key)}
                <li class="queue-row">
                  <span class="queue-idx mono">{i + 2}</span>
                  <span class="queue-name" title={item.title}>{item.title}</span>
                  {#if item.startTime}
                    <span class="time-chip mono">{item.startTime}</span>
                  {/if}
                  <span class={prioClass(item)}>{prioLabel(item)}</span>
                  <span class="row-actions">
                    <button class="btn btn-ghost do-now" onclick={() => promote(item)}>
                      <Zap size={12} />
                      {$t('executionPage.doNow')}
                    </button>
                    <button
                      class="btn btn-ghost btn-icon row-done"
                      disabled={busyKey === item.key}
                      aria-label={$t('executionPage.complete')}
                      title={$t('executionPage.complete')}
                      onclick={() => completeItem(item)}
                    >
                      <Check size={14} />
                    </button>
                  </span>
                </li>
              {/each}
            </ul>
          </section>
        {/if}
      {/if}
    </div>

    <SacredCalendar />
  </div>
</div>

<style>
  .execution-page {
    height: 100%;
    overflow-y: auto;
    padding: var(--s4) var(--s5);
    display: flex;
    flex-direction: column;
    gap: var(--s4);
  }

  .exec-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s3);
  }

  .exec-title {
    display: flex;
    align-items: center;
    gap: var(--s3);
  }

  .exec-title h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .context-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--s1_5);
    padding: 3px 10px;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--xp) 40%, var(--border));
    background: color-mix(in srgb, var(--xp) 10%, transparent);
    color: var(--xp);
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
  }

  .inbox-link {
    text-decoration: none;
  }

  .error-banner {
    padding: var(--s2) var(--s3);
    border: 1px solid color-mix(in srgb, #d9534f 50%, var(--border));
    background: color-mix(in srgb, #d9534f 12%, transparent);
    color: #d9534f;
    border-radius: var(--r);
    font-size: 12px;
  }

  .exec-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 300px;
    gap: var(--s4);
    align-items: start;
  }

  .exec-main {
    display: flex;
    flex-direction: column;
    gap: var(--s4);
    min-width: 0;
  }

  .exec-loading,
  .caption {
    font-size: 12px;
    color: var(--text-muted);
  }

  /* ── Hero ──────────────────────────────────────────────────────────────── */
  .hero {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    padding: var(--s5);
    border-color: color-mix(in srgb, var(--xp) 35%, var(--border));
    background:
      linear-gradient(135deg, color-mix(in srgb, var(--xp) 7%, transparent) 0%, transparent 45%),
      var(--surface);
  }

  .hero-kicker {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--s2);
  }

  .hero-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.18em;
    color: var(--xp);
    text-transform: uppercase;
  }

  .kind-chip,
  .ctx-chip {
    font-size: 10px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
    border: 1px solid var(--border);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .prio {
    font-size: 10px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 999px;
    border: 1px solid currentColor;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    white-space: nowrap;
  }
  .prio-goal {
    color: var(--xp);
  }
  .prio-urgent {
    color: #d9534f;
  }
  .prio-high {
    color: #e08c3a;
  }
  .prio-medium {
    color: var(--accent);
  }
  .prio-low {
    color: var(--text-muted);
  }

  .time-chip {
    font-size: 11px;
    color: var(--text-muted);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 2px 8px;
    white-space: nowrap;
  }

  .hero-title {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
    line-height: 1.25;
    color: var(--text-primary);
    overflow-wrap: anywhere;
  }

  .hero-progress {
    font-size: 12px;
  }

  .hero-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--s2);
    margin-top: var(--s1);
  }

  .hero-cta {
    font-size: 14px;
    padding: var(--s2_5) var(--s5);
    font-weight: 600;
  }

  .hero-focus-tools {
    display: flex;
    align-items: center;
    gap: var(--s1);
    margin-left: auto;
  }

  .btn.active {
    color: var(--xp);
    border-color: var(--xp);
  }

  /* ── Queue ─────────────────────────────────────────────────────────────── */
  .queue {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
  }

  .queue-title {
    margin: 0;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .queue-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s1);
  }

  .queue-row {
    display: flex;
    align-items: center;
    gap: var(--s3);
    padding: var(--s2) var(--s3);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    transition: border-color var(--t-fast);
    min-width: 0;
  }

  .queue-row:hover {
    border-color: color-mix(in srgb, var(--xp) 30%, var(--border));
  }

  .queue-idx {
    font-size: 11px;
    color: var(--text-muted);
    min-width: 16px;
    text-align: right;
    flex-shrink: 0;
  }

  .queue-name {
    flex: 1;
    font-size: 13px;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }

  .row-actions {
    display: flex;
    align-items: center;
    gap: var(--s1);
    flex-shrink: 0;
  }

  .do-now {
    font-size: 11px;
    padding: var(--s1) var(--s2);
  }

  .row-done {
    width: 26px;
    height: 26px;
    color: var(--text-muted);
  }

  .row-done:hover {
    color: var(--success);
    border-color: var(--success);
  }

  /* ── Onboarding ────────────────────────────────────────────────────────── */
  .onboarding {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    padding: var(--s5);
    max-width: 520px;
  }

  .onboarding-icon {
    color: var(--xp);
    opacity: 0.6;
  }

  .onboarding h4 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .onboarding-hint {
    margin: 0;
    font-size: 13px;
    color: var(--text-secondary);
  }

  .steps {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: var(--s2);
  }

  .steps li {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: var(--s2) var(--s3);
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--elevated);
  }

  .steps strong {
    font-size: 12px;
    color: var(--text-primary);
  }

  .steps span {
    font-size: 12px;
    color: var(--text-muted);
  }

  .onboarding .btn {
    align-self: flex-start;
    text-decoration: none;
  }

  @media (max-width: 900px) {
    .exec-layout {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 640px) {
    .hero-title {
      font-size: 19px;
    }
    .hero-focus-tools {
      margin-left: 0;
      width: 100%;
    }
    .queue-row {
      flex-wrap: wrap;
    }
    .queue-name {
      flex-basis: 100%;
      order: -1;
      margin-bottom: var(--s1);
    }
  }
</style>
