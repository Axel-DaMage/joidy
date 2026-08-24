<script lang="ts">
  import { browser } from '$app/environment';
  import { onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import { RefreshCw, CloudOff, CircleCheckBig, Loader } from 'lucide-svelte';
  import { t } from 'svelte-i18n';
  import { isOnline, pendingChanges, syncStatus, forceSync } from '$lib/stores/offlineSync';

  let showOnlinePill = false;
  let onlinePillTimer: ReturnType<typeof setTimeout> | null = null;

  let wasOffline = false;

  $: if (browser) {
    if (!$isOnline) {
      wasOffline = true;
      if (onlinePillTimer) {
        clearTimeout(onlinePillTimer);
        onlinePillTimer = null;
      }
      showOnlinePill = false;
    } else if (wasOffline) {
      showOnlinePill = true;
      if (onlinePillTimer) clearTimeout(onlinePillTimer);
      onlinePillTimer = setTimeout(() => {
        showOnlinePill = false;
        wasOffline = false;
      }, 3500);
    }
  }

  onMount(() => {
    return () => {
      if (onlinePillTimer) clearTimeout(onlinePillTimer);
    };
  });

  $: visible = browser && (!$isOnline || $syncStatus === 'syncing' || showOnlinePill);
</script>

{#if visible}
  <div
    class="offline-indicator"
    class:offline={!$isOnline}
    class:syncing={$syncStatus === 'syncing'}
    class:online={$isOnline && showOnlinePill}
    transition:fade={{ duration: 200 }}
  >
    {#if $syncStatus === 'syncing'}
      <Loader size={14} class="spin" />
      <span>{$t('offline.syncing')}</span>
    {:else if !$isOnline}
      <CloudOff size={14} />
      <span
        >{$t('offline.offline', {
          values: {
            pending: $pendingChanges,
            change:
              $pendingChanges === 1 ? $t('offline.pendingChange') : $t('offline.pendingChanges'),
          },
        })}</span
      >
      {#if $pendingChanges > 0}
        <button
          class="sync-btn"
          onclick={() => forceSync().catch(() => {})}
          aria-label={$t('offline.forceSync')}
        >
          <RefreshCw size={12} />
          {$t('offline.forceSync')}
        </button>
      {/if}
    {:else if showOnlinePill}
      <CircleCheckBig size={14} />
      <span>{$t('offline.online')}</span>
    {/if}
  </div>
{/if}

<style>
  .offline-indicator {
    position: fixed;
    bottom: 16px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 9000;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border-radius: 99px;
    font-size: 12px;
    font-weight: 500;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    transition: opacity 0.3s ease;
  }

  .offline-indicator.offline {
    background: color-mix(in srgb, var(--error, #ef4444) 12%, var(--elevated, #1a1a1a));
    border: 1px solid color-mix(in srgb, var(--error, #ef4444) 35%, transparent);
    color: var(--error, #ef4444);
  }

  .offline-indicator.syncing {
    background: color-mix(in srgb, var(--accent, #6366f1) 12%, var(--elevated, #1a1a1a));
    border: 1px solid color-mix(in srgb, var(--accent, #6366f1) 35%, transparent);
    color: var(--accent, #6366f1);
  }

  .offline-indicator.online {
    background: color-mix(in srgb, var(--success, #22c55e) 12%, var(--elevated, #1a1a1a));
    border: 1px solid color-mix(in srgb, var(--success, #22c55e) 35%, transparent);
    color: var(--success, #22c55e);
  }

  .sync-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: color-mix(in srgb, currentColor 15%, transparent);
    border: 1px solid color-mix(in srgb, currentColor 30%, transparent);
    color: inherit;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 99px;
    cursor: pointer;
    transition: background 0.2s;
  }
  .sync-btn:hover {
    background: color-mix(in srgb, currentColor 25%, transparent);
  }

  .spin {
    animation: spin 1s linear infinite;
  }
  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  @media (max-width: 600px) {
    .offline-indicator {
      bottom: 64px;
      max-width: calc(100vw - 32px);
      flex-wrap: wrap;
      justify-content: center;
    }
  }
</style>
