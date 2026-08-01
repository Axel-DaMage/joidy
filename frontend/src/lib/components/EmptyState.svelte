<script lang="ts">
  import type { Snippet } from 'svelte';

  /**
   * Shared empty-state component (#255).
   * Replaces duplicated empty-state markup across GoalList, StreakListPanel,
   * ChatInterface, GithubWidget, notes, goals, etc.
   */
  export let icon: Snippet | null = null;
  export let children: Snippet | null = null;
  export let title = '';
  export let message = '';
  export let actionLabel = '';
  export let onAction: (() => void) | null = null;
</script>

<div class="empty-state">
  {#if icon}
    <div class="empty-state-icon">
      {@render icon()}
    </div>
  {/if}
  {#if title}
    <h4 class="empty-state-title">{title}</h4>
  {/if}
  {#if message}
    <p class="empty-state-msg">{message}</p>
  {/if}
  {#if actionLabel && onAction}
    <button class="empty-state-action" onclick={onAction}>{actionLabel}</button>
  {/if}
  {#if children}
    {@render children()}
  {/if}
</div>

<style>
  .empty-state {
    padding: 32px;
    text-align: center;
    color: var(--text-muted);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  .empty-state-icon {
    opacity: 0.25;
    margin-bottom: 4px;
  }

  .empty-state-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-secondary);
  }

  .empty-state-msg {
    margin: 0;
    font-size: 13px;
    line-height: 1.4;
  }

  .empty-state-action {
    margin-top: 4px;
    background: none;
    border: none;
    color: var(--accent);
    font-size: 12px;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: var(--r-sm);
    transition: background var(--t-fast);
  }

  .empty-state-action:hover {
    background: var(--hover);
  }
</style>
