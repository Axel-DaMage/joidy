<script lang="ts">
  import { Pin, PinOff, Target, Clock, Tag, FileText, Settings } from 'lucide-svelte';
  import StreakIcon from './StreakIcon.svelte';

  export let goal: any;
  export let pinned: boolean = false;
  export let tags: any[] = [];
  export let notes: any[] = [];
  export let getGoalColor: (g: any) => string;
  export let TEMPORALITY_LABELS: Record<string, string>;
  export let STATE_LABELS: Record<string, string>;
  export let formatFailConfig: (c: string) => string;
  export let onTogglePin: (id: number) => void;
  export let onClick: (goal: any) => void;
</script>

<div
  class="goal-editor-card"
  class:completed={goal.state === 'COMPLETED' || goal.is_completed}
  class:failed={goal.state === 'FAILED'}
  class:paused={goal.state === 'PAUSED'}
  style="--goal-color: {getGoalColor(goal)}"
  role="button"
  tabindex="0"
  onclick={() => onClick(goal)}
  onkeydown={(e) => e.key === 'Enter' && onClick(goal)}
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
      <button
        class="pin-btn"
        class:pinned
        onclick={(e) => { e.stopPropagation(); onTogglePin(goal.id); }}
        title={pinned ? 'Desfijar' : 'Fijar'}
      >
        {#if pinned}
          <Pin size={14} fill="currentColor" />
        {:else}
          <PinOff size={14} />
        {/if}
      </button>
    </div>
    <div class="goal-state-indicator" class:active={goal.state === 'ACTIVE'} class:completed={goal.state === 'COMPLETED' || goal.is_completed} class:paused={goal.state === 'PAUSED'} class:failed={goal.state === 'FAILED'}>
      {STATE_LABELS[goal.state] || goal.state}
    </div>
  </div>
  <div class="card-title">{goal.title}</div>
  {#if goal.description}
    <div class="card-description">{goal.description.substring(0, 80)}{goal.description.length > 80 ? '...' : ''}</div>
  {/if}
  <div class="card-meta">
    <div class="meta-item">
      <Clock size={12} />
      <span>{TEMPORALITY_LABELS[goal.temporality] || goal.temporality}</span>
    </div>
    {#if goal.tag_id}
      <div class="meta-item">
        <Tag size={12} />
        <span>{tags.find(t => t.id === goal.tag_id)?.name || 'Etiqueta'}</span>
      </div>
    {:else if goal.note_id}
      <div class="meta-item">
        <FileText size={12} />
        <span>{notes.find(n => n.id === goal.note_id)?.title?.substring(0, 12) || 'Nota'}</span>
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
      <span class="progress-pct">{(goal.state === 'COMPLETED' || goal.is_completed) ? 100 : goal.progress_pct}%</span>
    </div>
    <div class="progress-bar">
      <div class="progress-fill" style="width: {(goal.state === 'COMPLETED' || goal.is_completed) ? 100 : goal.progress_pct}%"></div>
    </div>
  </div>
  <div class="card-footer">
    <span class="goal-id">#{goal.id}</span>
    {#if goal.created_at}
      <span class="goal-date">Creado: {goal.created_at.split('T')[0]}</span>
    {/if}
  </div>
</div>

<style>
  .goal-editor-card {
    background: var(--surface);
    border: 2px solid var(--goal-color);
    border-radius: 12px;
    padding: 20px;
    cursor: pointer;
    transition: all 0.25s ease;
    display: flex;
    flex-direction: column;
    gap: 12px;
    text-align: left;
    position: relative;
    overflow: hidden;
  }

  .goal-editor-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  }

  .goal-editor-card.completed {
    opacity: 0.7;
    border-color: var(--success);
  }

  .goal-editor-card.failed {
    border-color: var(--error);
    background: rgba(239, 68, 68, 0.03);
  }

  .goal-editor-card.paused {
    border-style: dashed;
    opacity: 0.6;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }

  .card-header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .pin-btn {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    background: var(--surface-hover);
    border: 1px solid var(--border);
    color: var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .pin-btn:hover {
    background: var(--surface-active);
    color: var(--accent);
  }

  .pin-btn.pinned {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
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
    background: rgba(251, 191, 36, 0.15);
    color: #fbbf24;
  }

  .goal-state-indicator.completed {
    background: rgba(16, 185, 129, 0.15);
    color: var(--success);
  }

  .goal-state-indicator.paused {
    background: rgba(245, 158, 11, 0.15);
    color: var(--warning);
  }

  .goal-state-indicator.failed {
    background: rgba(239, 68, 68, 0.15);
    color: var(--error);
  }

  .card-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .card-description {
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 4px;
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
    background: rgba(59, 130, 246, 0.1);
    color: #3b82f6;
  }

  .card-progress {
    margin-top: 8px;
    padding-top: 12px;
    border-top: 1px solid var(--border-light);
  }

  .progress-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
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

  .progress-bar {
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
  }

  .card-progress .progress-fill {
    height: 100%;
    background: var(--goal-color);
    border-radius: 3px;
    transition: width 0.3s ease;
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 10px;
    color: var(--text-disabled);
    margin-top: 4px;
  }

  .goal-id {
    font-family: var(--font-mono);
    font-weight: 600;
  }
</style>
