<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import ChatInterface from '$lib/components/ChatInterface.svelte';
  import DeadLetterQueue from '$lib/components/DeadLetterQueue.svelte';
  import { devMode } from '$lib/stores/settings';

  let usage = $state<{ ai_enabled: boolean; estimated_cost_usd: number } | null>(null);
  let loadingUsage = $state(true);

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
    <h2><DynamicIcon name="Brain" /> Inteligencia Artificial</h2>
    <div class="ai-status">
      {#if loadingUsage}
        <span class="status-pill muted">Verificando…</span>
      {:else if usage}
        <span class="status-pill" class:enabled={usage.ai_enabled} class:disabled={!usage.ai_enabled}>
          {usage.ai_enabled ? 'IA activa' : 'IA inactiva'}
        </span>
      {/if}
    </div>
  </div>

  <div class="ai-content">
    <ChatInterface />
  </div>

  {#if $devMode}
    <details class="dev-section">
      <summary>Modo dev — Estado del servicio & cola de errores</summary>
      <div class="dev-grid">
        <div class="dev-card">
          <h3><DynamicIcon name="Activity" /> Estado del servicio</h3>
          {#if usage}
            <p class="stat">
              <span class="stat-label">API Key configurada:</span>
              <span class="stat-value" class:enabled={usage.ai_enabled} class:disabled={!usage.ai_enabled}>
                {usage.ai_enabled ? 'Sí' : 'No'}
              </span>
            </p>
            <p class="stat">
              <span class="stat-label">Costo estimado:</span>
              <span class="stat-value">${usage.estimated_cost_usd.toFixed(4)} USD</span>
            </p>
          {:else}
            <p class="muted">No se pudo obtener el estado.</p>
          {/if}
        </div>
        <DeadLetterQueue />
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
  .stat-value.enabled { color: var(--success, #10b981); }
  .stat-value.disabled { color: var(--error, #ef4444); }
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
</style>
