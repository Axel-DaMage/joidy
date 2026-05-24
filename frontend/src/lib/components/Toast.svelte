<script lang="ts">
  import { notifications, dismissNotification } from '$lib/stores/notifications';
  import { fly } from 'svelte/transition';
  import DynamicIcon from './DynamicIcon.svelte';
</script>

{#if $notifications.length > 0}
  <div class="toast-container">
    {#each $notifications as notif (notif.id)}
      <button 
        class="toast toast-{notif.type}"
        transition:fly={{ y: -20, duration: 200 }}
        on:click={() => dismissNotification(notif.id)}
      >
        <DynamicIcon 
          name={notif.type === 'success' ? 'CheckCircle' : notif.type === 'level' ? 'TrendingUp' : notif.type === 'error' ? 'AlertTriangle' : 'Info'} 
          size={16} 
        />
        <span class="toast-message">{notif.message}</span>
      </button>
    {/each}
  </div>
{/if}

<style>
  .toast-container {
    position: fixed;
    top: 16px;
    right: 16px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 8px;
    pointer-events: none;
  }

  .toast {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border-radius: var(--r, 8px);
    font-size: 13px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    pointer-events: auto;
    max-width: 320px;
    background: var(--elevated, #1a1a1a);
    border: 1px solid var(--border);
    cursor: pointer;
  }
  .toast:hover {
    opacity: 0.85;
  }

  .toast-message {
    color: var(--text-primary, #e0e0e0);
    line-height: 1.3;
  }

  .toast-info {
    border-color: var(--accent, #6366f1);
  }
  .toast-info :global(svg) {
    color: var(--accent, #6366f1);
  }

  .toast-success {
    border-color: var(--success, #22c55e);
    background: color-mix(in srgb, var(--success, #22c55e) 10%, var(--elevated, #1a1a1a));
  }
  .toast-success :global(svg) {
    color: var(--success, #22c55e);
  }

  .toast-level {
    border-color: var(--xp, #f59e0b);
    background: linear-gradient(135deg, color-mix(in srgb, var(--xp, #f59e0b) 15%, var(--elevated, #1a1a1a)), transparent);
  }
  .toast-level :global(svg) {
    color: var(--xp, #f59e0b);
  }

  .toast-error {
    border-color: var(--error, #ef4444);
    background: color-mix(in srgb, var(--error, #ef4444) 10%, var(--elevated, #1a1a1a));
  }
  .toast-error :global(svg) {
    color: var(--error, #ef4444);
  }
</style>