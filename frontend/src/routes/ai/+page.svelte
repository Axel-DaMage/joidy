<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import { devMode } from '$lib/stores/settings';
  import { t } from 'svelte-i18n';

  let usage = $state<{ ai_enabled: boolean; estimated_cost_usd: number } | null>(null);
  let loadingUsage = $state(true);

  // Lazy-load the heavy ChatInterface (376 lines, pulls in marked, dompurify)
  // so it is split into a separate chunk and only downloaded when the AI page
  // is opened (#347).
  let ChatInterface = $state<typeof import('$lib/components/ChatInterface.svelte').default | null>(
    null
  );
  $effect(() => {
    if (!ChatInterface) {
      import('$lib/components/ChatInterface.svelte').then((m) => (ChatInterface = m.default));
    }
  });

  // Lazy-load DeadLetterQueue — only shown in dev mode, so defer the chunk
  // until the user actually enables it (#347).
  let DeadLetterQueue: typeof import('$lib/components/DeadLetterQueue.svelte').default | null =
    null;
  $effect(() => {
    if ($devMode && !DeadLetterQueue) {
      import('$lib/components/DeadLetterQueue.svelte').then((m) => (DeadLetterQueue = m.default));
    }
  });

  onMount(async () => {
    try {
      usage = await api.ai.usage();
    } catch {
      usage = null;
    } finally {
      loadingUsage = false;
    }
  });
</script>

<div class="ai-page">
  <div class="ai-header">
    <h2><DynamicIcon name="Brain" /> {$t('ai.title')}</h2>
    <div class="ai-status">
      {#if loadingUsage}
        <span class="status-pill muted">{$t('ai.checking')}</span>
      {:else if usage}
        <span
          class="status-pill"
          class:enabled={usage.ai_enabled}
          class:disabled={!usage.ai_enabled}
        >
          {usage.ai_enabled ? $t('ai.active') : $t('ai.inactive')}
        </span>
      {/if}
    </div>
  </div>

  <div class="ai-content">
    {#if ChatInterface}
      <svelte:component this={ChatInterface} />
    {:else}
      <div class="caption" style="padding: 24px; text-align: center; color: var(--text-muted);">
        {$t('ai.loadingChat')}
      </div>
    {/if}
  </div>

  {#if $devMode}
    <details class="dev-section">
      <summary>{$t('ai.devSection')}</summary>
      <div class="dev-grid">
        <div class="dev-card">
          <h3><DynamicIcon name="Activity" /> {$t('ai.serviceStatus')}</h3>
          {#if usage}
            <p class="stat">
              <span class="stat-label">{$t('ai.apiKeyConfigured')}</span>
              <span
                class="stat-value"
                class:enabled={usage.ai_enabled}
                class:disabled={!usage.ai_enabled}
              >
                {usage.ai_enabled ? $t('ai.yes') : $t('ai.no')}
              </span>
            </p>
            <p class="stat">
              <span class="stat-label">{$t('ai.estimatedCost')}</span>
              <span class="stat-value">${usage.estimated_cost_usd.toFixed(4)} USD</span>
            </p>
          {:else}
            <p class="muted">{$t('ai.statusUnavailable')}</p>
          {/if}
        </div>
        {#if DeadLetterQueue}<svelte:component this={DeadLetterQueue} />{/if}
      </div>
    </details>
  {/if}
</div>

<style>
  .ai-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    padding: var(--s4, 16px);
    max-width: 900px;
    margin: 0 auto;
    width: 100%;
    box-sizing: border-box;
  }
  .ai-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--s3, 12px);
    flex-shrink: 0;
  }
  .ai-header h2 {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0;
    font-size: 1.1rem;
  }
  .ai-status {
    display: flex;
    align-items: center;
  }
  .status-pill {
    font-size: 0.75rem;
    padding: 3px var(--s2, 8px);
    border-radius: var(--r-full, 999px);
    border: 1px solid var(--border, #1a1a1a);
  }
  .status-pill.enabled {
    color: var(--success, #10b981);
    border-color: var(--success, #10b981);
  }
  .status-pill.disabled {
    color: var(--error, #ef4444);
    border-color: var(--error, #ef4444);
  }
  .status-pill.muted {
    color: var(--text-muted, #888);
  }
  .ai-content {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .dev-section {
    flex-shrink: 0;
    margin-top: var(--s3, 12px);
    border-top: 1px solid var(--border, #1a1a1a);
    padding-top: var(--s3, 12px);
  }
  .dev-section summary {
    cursor: pointer;
    color: var(--text-muted, #888);
    font-size: 0.8rem;
    padding: var(--s2, 8px) 0;
  }
  .dev-grid {
    display: flex;
    flex-direction: column;
    gap: var(--s3, 12px);
    padding-top: var(--s2, 8px);
  }
  .dev-card h3 {
    margin: 0 0 12px;
    font-size: 0.95rem;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .stat {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
    margin: 0;
    font-size: 0.875rem;
  }
  .stat-label {
    color: var(--text-muted, #888);
  }
  .stat-value.enabled {
    color: var(--success, #10b981);
  }
  .stat-value.disabled {
    color: var(--error, #ef4444);
  }
  .muted {
    color: var(--text-muted, #888);
    font-size: 0.85rem;
  }
  @media (max-width: 768px) {
    .ai-page {
      padding: var(--s3, 12px);
    }
    .ai-header h2 {
      font-size: 1rem;
    }
  }
  .stat-value.enabled {
    color: var(--color-success, #38a169);
  }
  .stat-value.disabled {
    color: var(--color-error, #e53e3e);
  }

  /* ── Responsive ── */
  @media (max-width: 768px) {
    .ai-page {
      padding: var(--s4, 1rem);
      max-width: 100%;
    }

    .ai-page h2 {
      font-size: 1.1rem;
      margin-bottom: var(--s3, 0.75rem);
    }

    .ai-grid {
      gap: var(--s3, 0.75rem);
    }

    .stat {
      flex-direction: column;
      align-items: flex-start;
      gap: 2px;
    }
  }

  @media (max-width: 480px) {
    .ai-page {
      padding: var(--s3, 0.75rem);
    }

    .ai-page h2 {
      font-size: 1rem;
      gap: 6px;
    }

    .muted {
      padding: var(--s3, 0.75rem) 0;
    }
  }
</style>
