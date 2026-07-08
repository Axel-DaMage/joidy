<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';

  let {
    icon = 'Inbox',
    title = 'No hay datos',
    description = '',
    action = null,
    actionHref = '',
    onAction = null
  }: {
    icon?: string;
    title?: string;
    description?: string;
    action?: string | null;
    actionHref?: string;
    onAction?: (() => void) | null;
  } = $props();
</script>

<div class="empty-state">
  <div class="empty-icon">
    <DynamicIcon name={icon} size={32} color="var(--text-muted)" />
  </div>
  <h4 class="empty-title">{title}</h4>
  {#if description}
    <p class="empty-desc">{description}</p>
  {/if}
  {#if action}
    {#if actionHref}
      <a href={actionHref} class="empty-action">{action}</a>
    {:else if onAction}
      <button class="empty-action" onclick={onAction}>{action}</button>
    {/if}
  {/if}
</div>

<style>
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 32px 16px;
    text-align: center;
  }

  .empty-icon {
    margin-bottom: 12px;
    opacity: 0.5;
  }

  .empty-title {
    margin: 0 0 6px 0;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-secondary);
  }

  .empty-desc {
    margin: 0 0 16px 0;
    font-size: 12px;
    color: var(--text-muted);
    max-width: 240px;
  }

  .empty-action {
    font-size: 12px;
    color: var(--accent);
    text-decoration: none;
    padding: 6px 12px;
    border-radius: var(--r);
    background: color-mix(in srgb, var(--accent) 10%, transparent);
    transition: all var(--t-fast);
    border: none;
    cursor: pointer;
  }

  .empty-action:hover {
    background: color-mix(in srgb, var(--accent) 20%, transparent);
  }
</style>
