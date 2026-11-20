<script lang="ts">
  import { notifications, dismissNotification } from '$lib/stores/notifications';
  import { fly } from 'svelte/transition';
  import DynamicIcon from './DynamicIcon.svelte';

  // Map each notification type to its icon name and accent color. Passing the
  // color explicitly to DynamicIcon avoids the inline `color: inherit` style
  // (set by DynamicIcon when no color prop is given) from overriding the
  // `:global(svg)` CSS rules — which left icons uncolored and low-contrast in
  // dark mode (#793).
  const TYPE_CONFIG: Record<string, { icon: string; color: string }> = {
    success: { icon: 'CircleCheckBig', color: 'var(--success, #10b981)' },
    level: { icon: 'TrendingUp', color: 'var(--xp, #c8a96e)' },
    error: { icon: 'TriangleAlert', color: 'var(--error, #ef4444)' },
    info: { icon: 'Info', color: 'var(--accent, #e0e0e0)' },
  };
</script>

{#if $notifications.length > 0}
  <div class="toast-container">
    {#each $notifications as notif (notif.id)}
      {@const cfg = TYPE_CONFIG[notif.type] ?? TYPE_CONFIG.info}
      {#if notif.href}
        <a
          class="toast toast-{notif.type}"
          href={notif.href}
          transition:fly={{ y: -20, duration: 200 }}
          onclick={() => dismissNotification(notif.id)}
        >
          <DynamicIcon name={cfg.icon} size={16} color={cfg.color} />
          <span class="toast-message">{notif.message}</span>
        </a>
      {:else}
        <button
          class="toast toast-{notif.type}"
          transition:fly={{ y: -20, duration: 200 }}
          onclick={() => dismissNotification(notif.id)}
        >
          <DynamicIcon name={cfg.icon} size={16} color={cfg.color} />
          <span class="toast-message">{notif.message}</span>
        </button>
      {/if}
    {/each}
  </div>
{/if}

<style>
  .toast-container {
    position: fixed;
    top: 16px;
    right: 16px;
    z-index: var(--z-toast);
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
    border-radius: var(--r, 4px);
    font-size: 13px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    pointer-events: auto;
    max-width: 320px;
    background: var(--elevated, #161616);
    border: 1px solid var(--border);
    cursor: pointer;
  }
  .toast:hover {
    opacity: 0.85;
  }
  a.toast {
    text-decoration: none;
    color: inherit;
  }

  .toast-message {
    color: var(--text-primary, #ffffff);
    line-height: 1.3;
  }

  .toast-info {
    border-color: var(--accent, #e0e0e0);
  }
  .toast-info :global(svg) {
    color: var(--accent, #e0e0e0);
  }

  .toast-success {
    border-color: var(--success, #10b981);
    background: color-mix(in srgb, var(--success, #10b981) 10%, var(--elevated, #161616));
  }
  .toast-success :global(svg) {
    color: var(--success, #10b981);
  }

  .toast-level {
    border-color: var(--xp, #c8a96e);
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--xp, #c8a96e) 15%, var(--elevated, #161616)),
      transparent
    );
  }
  .toast-level :global(svg) {
    color: var(--xp, #c8a96e);
  }

  .toast-error {
    border-color: var(--error, #ef4444);
    background: color-mix(in srgb, var(--error, #ef4444) 10%, var(--elevated, #161616));
  }
  .toast-error :global(svg) {
    color: var(--error, #ef4444);
  }
</style>
