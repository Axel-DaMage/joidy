<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import Card from '$lib/components/Card.svelte';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
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
  <h2><DynamicIcon icon="Brain" /> Inteligencia Artificial</h2>

  <div class="ai-grid">
    <Card padding="md">
      <h3><DynamicIcon icon="Activity" /> Estado del servicio</h3>
      {#if loadingUsage}
        <p class="muted">Verificando...</p>
      {:else if usage}
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
    </Card>

    {#if $devMode}
      <DeadLetterQueue />
    {/if}
  </div>
</div>

<style>
  .ai-page {
    padding: 24px;
    max-width: 800px;
    margin: 0 auto;
  }
  .ai-page h2 {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 0 20px;
  }
  .ai-grid {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  :global(.ai-grid) h3 {
    margin: 0 0 12px;
    font-size: 0.95rem;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .muted {
    color: var(--color-muted, #888);
    font-size: 0.85rem;
    text-align: center;
    padding: 16px 0;
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
    color: var(--color-muted, #888);
  }
  .stat-value.enabled { color: var(--color-success, #38a169); }
  .stat-value.disabled { color: var(--color-error, #e53e3e); }
</style>
