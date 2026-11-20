<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import BetaBanner from '$lib/components/BetaBanner.svelte';
  import AiDisclosure from '$lib/components/AiDisclosure.svelte';
  import { aiStatusFromUsage } from '$lib/utils/aiStatus';
  import { logger } from '$lib/utils/logger';
  import { t } from 'svelte-i18n';

  let usage = $state<Awaited<ReturnType<typeof api.ai.usage>> | null>(null);
  let loadingUsage = $state(true);

  // Effective pill status (#1460): consumes the backend's real reachability
  // report (ai_status) when present, falls back to the ai_enabled env flag
  // on older backends.
  let aiStatus = $derived(aiStatusFromUsage(usage));

  // Lazy-load the heavy ChatInterface (376 lines, pulls in marked, dompurify)
  // so it is split into a separate chunk and only downloaded when the AI page
  // is opened (#347). A failed import must surface an error + retry — never
  // an infinite "Cargando chat…" (#1459).
  let ChatInterface = $state<typeof import('$lib/components/ChatInterface.svelte').default | null>(
    null
  );
  let chatLoadError = $state(false);
  let chatLoading = $state(false);
  function loadChatInterface() {
    if (ChatInterface || chatLoading) return;
    chatLoading = true;
    chatLoadError = false;
    import('$lib/components/ChatInterface.svelte')
      .then((m) => (ChatInterface = m.default))
      .catch((err) => {
        logger.error('[ai] ChatInterface chunk failed:', err);
        chatLoadError = true;
      })
      .finally(() => (chatLoading = false));
  }
  $effect(() => {
    if (!ChatInterface && !chatLoadError) loadChatInterface();
  });

  // Lazy-load DeadLetterQueue — it lives inside a collapsed <details>, so
  // defer the chunk until it is actually rendered (#347).
  let DeadLetterQueue = $state<typeof import('$lib/components/DeadLetterQueue.svelte').default | null>(
    null
  );
  let dlqLoadError = $state(false);
  let dlqLoading = $state(false);
  function loadDeadLetterQueue() {
    if (DeadLetterQueue || dlqLoading) return;
    dlqLoading = true;
    dlqLoadError = false;
    import('$lib/components/DeadLetterQueue.svelte')
      .then((m) => (DeadLetterQueue = m.default))
      .catch((err) => {
        logger.error('[ai] DeadLetterQueue chunk failed:', err);
        dlqLoadError = true;
      })
      .finally(() => (dlqLoading = false));
  }
  $effect(() => {
    if (!DeadLetterQueue && !dlqLoadError) loadDeadLetterQueue();
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
  <BetaBanner />
  <div class="ai-header">
    <h2><DynamicIcon name="Brain" /> {$t('ai.title')}</h2>
    <div class="ai-status">
      {#if loadingUsage}
        <span class="status-pill muted">{$t('ai.checking')}</span>
      {:else if usage}
        <span
          class="status-pill"
          class:enabled={aiStatus === 'ok'}
          class:degraded={aiStatus === 'degraded'}
          class:disabled={aiStatus === 'unavailable' || aiStatus === 'disabled'}
          title={usage.ai_status_detail ?? undefined}
        >
          {aiStatus === 'ok'
            ? $t('ai.active')
            : aiStatus === 'degraded'
              ? $t('ai.degraded')
              : aiStatus === 'unavailable'
                ? $t('ai.unavailable')
                : $t('ai.inactive')}
        </span>
      {/if}
    </div>
  </div>

  <AiDisclosure />

  <div class="ai-content">
    {#if ChatInterface}
      <ChatInterface />
    {:else if chatLoadError}
      <div
        class="caption"
        style="padding: 24px; text-align: center; color: var(--text-muted); display: flex; flex-direction: column; align-items: center; gap: 10px;"
      >
        <span>{$t('ai.chatLoadError')}</span>
        <button class="btn btn-ghost" onclick={loadChatInterface}>{$t('common.retry')}</button>
      </div>
    {:else}
      <div class="caption" style="padding: 24px; text-align: center; color: var(--text-muted);">
        {$t('ai.loadingChat')}
      </div>
    {/if}
  </div>

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
      {#if DeadLetterQueue}
        <DeadLetterQueue />
      {:else if dlqLoadError}
        <div class="dev-card">
          <p class="muted">
            {$t('common.loadFailed')}
            <button class="btn btn-ghost" onclick={loadDeadLetterQueue}>
              {$t('common.retry')}
            </button>
          </p>
        </div>
      {/if}
    </div>
  </details>
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
  /* Degraded: primary provider down, fallback serving (#1460) */
  .status-pill.degraded {
    color: var(--warning, #f59e0b);
    border-color: var(--warning, #f59e0b);
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
