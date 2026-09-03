<script lang="ts">
  import { Pin, PinOff, Target, Clock, Tag, FileText, Settings, CheckCircle2, Trash2 } from 'lucide-svelte';
  import StreakIcon from './StreakIcon.svelte';
  import ProgressBar from './ProgressBar.svelte';
  import { getGoalContext } from '$lib/stores/goalContext';
  import { t } from 'svelte-i18n';

  export let goal: any;
  export let pinned: boolean = false;

  // Consume the shared goal context instead of receiving 9 props from the
  // parent (#351). Falls back to no-op defaults if used outside a provider.
  const ctx = getGoalContext() ?? {
    tags: [] as any[],
    notes: [] as any[],
    getGoalColor: (_g: any) => '#c8a96e',
    TEMPORALITY_LABELS: {} as Record<string, string>,
    STATE_LABELS: {} as Record<string, string>,
    formatFailConfig: (_c: string) => '',
    onTogglePin: (_id: number) => {},
    onClick: (_g: any) => {},
    onComplete: undefined,
    onDelete: undefined,
  };
  const {
    tags,
    notes,
    getGoalColor,
    TEMPORALITY_LABELS,
    STATE_LABELS,
    formatFailConfig,
    onTogglePin,
    onClick,
    onComplete,
    onDelete,
  } = ctx;

  // Build Maps for O(1) lookups instead of linear searches
  const tagsMap = new Map(tags.map((t) => [t.id, t]));
  const notesMap = new Map(notes.map((n) => [n.id, n]));

  let deleteConfirming = false;
  let deleteTimer: ReturnType<typeof setTimeout> | null = null;

  function handleDeleteClick(id: number) {
    if (!deleteConfirming) {
      deleteConfirming = true;
      deleteTimer = setTimeout(() => (deleteConfirming = false), 3000);
      return;
    }
    if (deleteTimer) clearTimeout(deleteTimer);
    deleteConfirming = false;
    onDelete?.(id);
  }
</script>

<div
  class="goal-editor-card"
  class:completed={goal.state === 'COMPLETED' || goal.is_completed}
  class:failed={goal.state === 'FAILED'}
  class:paused={goal.state === 'PAUSED'}
  style="--goal-color: {getGoalColor(goal)}"
>
  <button
    class="goal-card-main"
    onclick={() => onClick(goal)}
    aria-label={$t('goalCard.openGoal', { values: { title: goal.title } })}
  >
    <div class="card-header">
      <div class="card-header-left">
        <div class="goal-icon">
          {#if goal.fail_emoji}
            <StreakIcon name={goal.fail_emoji} size={24} color={getGoalColor(goal)} />
          {:else}
            <Target size={20} color={getGoalColor(goal)} />
          {/if}
        </div>
      </div>
    </div>
    <div class="card-title">{goal.title}</div>
    <div
      class="goal-state-indicator"
      class:active={goal.state === 'ACTIVE'}
      class:completed={goal.state === 'COMPLETED' || goal.is_completed}
      class:paused={goal.state === 'PAUSED'}
      class:failed={goal.state === 'FAILED'}
    >
      {STATE_LABELS[goal.state] || goal.state}
    </div>
    {#if goal.description}
      <div class="card-description">
        {goal.description.substring(0, 80)}{goal.description.length > 80 ? '...' : ''}
      </div>
    {/if}
    <div class="card-meta">
      <div class="meta-item">
        <Clock size={12} />
        <span>{TEMPORALITY_LABELS[goal.temporality] || goal.temporality}</span>
      </div>
      {#if goal.tag_id}
        <div class="meta-item">
          <Tag size={12} />
          <span>{tagsMap.get(goal.tag_id)?.name || 'Etiqueta'}</span>
        </div>
      {:else if goal.note_id}
        <div class="meta-item">
          <FileText size={12} />
          <span>{notesMap.get(goal.note_id)?.title?.substring(0, 12) || 'Nota'}</span>
        </div>
      {/if}
      {#if goal.fail_config !== 'STATIC'}
        <div class="meta-item config">
          <Settings size={12} />
          <span>{formatFailConfig(goal.fail_config)}</span>
        </div>
      {/if}
    </div>
    <div class="card-progress">
      <div class="progress-info">
        <span class="progress-text">
          {#if goal.measurement_type === 'BOOLEAN'}
            {goal.current_value >= 1 ? 'Completado' : 'Pendiente'}
          {:else if goal.measurement_type === 'PERCENT'}
            {goal.current_value}%
          {:else}
            {goal.current_value} / {goal.target_value}
          {/if}
        </span>
        <span class="progress-pct"
          >{goal.state === 'COMPLETED' || goal.is_completed ? 100 : goal.progress_pct}%</span
        >
      </div>
      <ProgressBar
        value={goal.state === 'COMPLETED' || goal.is_completed ? 100 : goal.progress_pct}
        color="var(--goal-color)"
        height={6}
      />
    </div>
    <div class="card-footer">
      <span class="goal-id">#{goal.id}</span>
      {#if goal.created_at}
        <span class="goal-date"
          >{$t('goalCard.created', { values: { date: goal.created_at.split('T')[0] } })}</span
        >
      {/if}
    </div>
  </button>
  <div class="card-actions-bar">
    {#if onComplete}
      <button
        class="card-action-btn complete-btn"
        class:completed={goal.state === 'COMPLETED' || goal.is_completed}
        onclick={(e) => { e.stopPropagation(); onComplete?.(goal.id); }}
        title={goal.state === 'COMPLETED' || goal.is_completed ? 'Marcar como pendiente' : 'Completar objetivo'}
        aria-label="Completar objetivo"
      >
        <CheckCircle2 size={14} />
      </button>
    {/if}

    {#if onDelete}
      <button
        class="card-action-btn delete-btn"
        class:confirming={deleteConfirming}
        onclick={(e) => { e.stopPropagation(); handleDeleteClick(goal.id); }}
        title={deleteConfirming ? 'Haz clic de nuevo para eliminar' : 'Eliminar objetivo'}
        aria-label="Eliminar objetivo"
      >
        <Trash2 size={14} />
      </button>
    {/if}

    <button
      class="card-action-btn pin-btn"
      class:pinned
      onclick={(e) => { e.stopPropagation(); onTogglePin(goal.id); }}
      title={pinned ? 'Desfijar' : 'Fijar'}
      aria-label={pinned ? 'Desfijar objetivo' : 'Fijar objetivo'}
    >
      {#if pinned}
        <Pin size={14} fill="currentColor" />
      {:else}
        <PinOff size={14} />
      {/if}
    </button>
  </div>
</div>

<style>
  .goal-editor-card {
    background: var(--surface);
    border: 2px solid var(--goal-color);
    border-radius: 12px;
    padding: 14px 16px;
    transition: all 0.25s ease;
    display: flex;
    flex-direction: column;
    gap: 8px;
    text-align: center;
    position: relative;
    overflow: hidden;
    aspect-ratio: 1;
  }

  .goal-card-main {
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    text-align: center;
    color: inherit;
    font: inherit;
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
    align-items: center;
  }

  .goal-editor-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px color-mix(in srgb, var(--text-primary) 15%, transparent);
  }

  .goal-editor-card.completed {
    opacity: 0.7;
    border-color: var(--success);
  }

  .goal-editor-card.failed {
    border-color: var(--error);
    background: color-mix(in srgb, var(--error) 3%, transparent);
  }

  .goal-editor-card.paused {
    border-style: dashed;
    opacity: 0.6;
  }

  .card-header {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 8px;
    position: relative;
  }

  .card-header-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .card-actions-bar {
    position: absolute;
    top: 8px;
    right: 8px;
    display: flex;
    align-items: center;
    gap: 4px;
    z-index: 15;
    opacity: 1;
    transition: opacity 0.2s ease;
  }

  .card-action-btn {
    width: 26px;
    height: 26px;
    border-radius: 6px;
    background: var(--elevated, var(--surface));
    border: 1px solid var(--border);
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s ease;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
  }

  .card-action-btn:hover {
    background: var(--surface-active);
    color: var(--text-primary);
  }

  .complete-btn:hover {
    color: var(--success, #22c55e);
    border-color: var(--success, #22c55e);
  }

  .complete-btn.completed {
    background: var(--success, #22c55e);
    border-color: var(--success, #22c55e);
    color: #ffffff;
  }

  .delete-btn:hover {
    color: #ef4444;
    border-color: #ef4444;
  }

  .delete-btn.confirming {
    background: #ef4444;
    border-color: #ef4444;
    color: #ffffff;
  }

  .pin-btn.pinned {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
    opacity: 1;
  }

  .goal-icon {
    width: 44px;
    height: 44px;
    border-radius: 10px;
    background: color-mix(in srgb, var(--goal-color) 15%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .goal-state-indicator {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 4px 8px;
    border-radius: 4px;
    background: var(--surface-hover);
    color: var(--text-muted);
  }

  .goal-state-indicator.active {
    background: color-mix(in srgb, var(--today) 15%, transparent);
    color: var(--today);
  }

  .goal-state-indicator.completed {
    background: color-mix(in srgb, var(--success) 15%, transparent);
    color: var(--success);
  }

  .goal-state-indicator.paused {
    background: color-mix(in srgb, var(--warning) 15%, transparent);
    color: var(--warning);
  }

  .goal-state-indicator.failed {
    background: color-mix(in srgb, var(--error) 15%, transparent);
    color: var(--error);
  }

  .card-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-clamp: 2;
    overflow: hidden;
    text-align: center;
  }

  .card-description {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 1;
    -webkit-box-orient: vertical;
    line-clamp: 1;
    overflow: hidden;
    text-align: center;
  }

  .card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 2px;
    justify-content: center;
  }

  .meta-item {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--text-muted);
    padding: 4px 8px;
    background: var(--surface-hover);
    border-radius: 4px;
  }

  .meta-item.config {
    background: color-mix(in srgb, var(--link) 10%, transparent);
    color: var(--link);
  }

  .card-progress {
    margin-top: 4px;
    padding-top: 8px;
    border-top: 1px solid var(--border-light);
    width: 100%;
  }

  .progress-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }

  .progress-text {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
    font-family: var(--font-mono);
  }

  .progress-pct {
    font-size: 12px;
    font-weight: 600;
    color: var(--goal-color);
    font-family: var(--font-mono);
  }

  .card-footer {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 8px;
    font-size: 10px;
    color: var(--text-disabled);
    margin-top: 2px;
  }

  .goal-id {
    font-family: var(--font-mono);
    font-weight: 600;
  }
</style>
