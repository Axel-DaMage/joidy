<script lang="ts">
  import { onMount } from 'svelte';
  import DynamicIcon from './DynamicIcon.svelte';
  import { api } from '$lib/api';
  import { showNotification } from '$lib/stores/notifications';

  let powerStatus: {
    docker_available: boolean;
    services: {
      name: string;
      status: 'running' | 'stopped' | 'unknown';
      healthy: boolean | null;
    }[];
    hibernating: boolean;
  } | null = $state(null);
  let powerLoading = $state(false);
  let powerActionLoading: 'sleep' | 'wake' | 'shutdown' | null = $state(null);
  let powerError = $state('');
  let powerMessage = $state('');
  let shutdownConfirm = $state(false);

  const SERVICE_LABELS: Record<string, string> = {
    postgres: 'PostgreSQL',
    api: 'API',
    'ai-service': 'AI Service',
    worker: 'Worker',
    frontend: 'Frontend',
  };

  onMount(async () => {
    await loadPowerStatus();
  });

  async function loadPowerStatus() {
    powerLoading = true;
    powerError = '';
    try {
      powerStatus = await api.power.status();
    } catch (e: any) {
      powerStatus = null;
      powerError = e.message || 'No se pudo obtener el estado de los servicios';
    } finally {
      powerLoading = false;
    }
  }

  async function hibernateServices() {
    powerActionLoading = 'sleep';
    powerError = '';
    powerMessage = '';
    try {
      const result = await api.power.sleep();
      powerMessage = result.message;
      showNotification(result.message, 'success');
      await loadPowerStatus();
    } catch (e: any) {
      powerError = e.message || 'Error al hibernar servicios';
      showNotification(powerError, 'error');
    } finally {
      powerActionLoading = null;
    }
  }

  async function wakeServices() {
    powerActionLoading = 'wake';
    powerError = '';
    powerMessage = '';
    try {
      const result = await api.power.wake();
      powerMessage = result.message;
      showNotification(result.message, 'success');
      await loadPowerStatus();
    } catch (e: any) {
      powerError = e.message || 'Error al despertar servicios';
      showNotification(powerError, 'error');
    } finally {
      powerActionLoading = null;
    }
  }

  async function shutdownServices() {
    powerActionLoading = 'shutdown';
    powerError = '';
    powerMessage = '';
    try {
      const result = await api.power.shutdown();
      powerMessage = result.message;
      showNotification(result.message, 'info');
      await loadPowerStatus();
    } catch (e: any) {
      powerError = e.message || 'Error al apagar servicios';
      showNotification(powerError, 'error');
    } finally {
      powerActionLoading = null;
      shutdownConfirm = false;
    }
  }
</script>

<!-- Servicios (Power Management) -->
<section class="section">
  <div class="section-title" style="color: var(--xp, var(--accent));">
    <DynamicIcon name="Power" size={12} /> Servicios
  </div>

  {#if powerLoading}
    <p class="hint">Cargando estado de servicios…</p>
  {:else if !powerStatus || !powerStatus.docker_available}
    <p class="hint">
      Docker no está disponible. Usa la CLI (<span class="mono">joidy down</span>) para detener
      servicios.
    </p>
  {:else}
    <!-- Service status list -->
    <div class="power-service-list">
      {#each powerStatus.services as svc}
        <div class="power-service-row">
          <span class="power-service-name">{SERVICE_LABELS[svc.name] || svc.name}</span>
          <span
            class="power-service-badge"
            class:running={svc.status === 'running'}
            class:stopped={svc.status !== 'running'}
          >
            {#if svc.status === 'running'}
              {#if svc.healthy === false}
                ⚠ unhealthy
              {:else}
                ● running
              {/if}
            {:else}
              ○ stopped
            {/if}
          </span>
        </div>
      {/each}
    </div>

    {#if powerError}
      <p class="hint" style="color: var(--error);">{powerError}</p>
    {/if}
    {#if powerMessage}
      <p class="hint" style="color: var(--success);">{powerMessage}</p>
    {/if}

    <!-- Action buttons -->
    <div class="power-actions">
      {#if powerStatus.hibernating}
        <button
          class="power-btn wake"
          onclick={wakeServices}
          disabled={powerActionLoading !== null}
        >
          {#if powerActionLoading === 'wake'}
            <DynamicIcon name="LoaderCircle" size={12} /> Despertando…
          {:else}
            <DynamicIcon name="Sun" size={12} /> Despertar
          {/if}
        </button>
      {:else}
        <button
          class="power-btn sleep"
          onclick={hibernateServices}
          disabled={powerActionLoading !== null}
          title="Detiene AI Service y Worker para ahorrar recursos"
        >
          {#if powerActionLoading === 'sleep'}
            <DynamicIcon name="LoaderCircle" size={12} /> Hibernando…
          {:else}
            <DynamicIcon name="Moon" size={12} /> Hibernar
          {/if}
        </button>
      {/if}

      {#if !shutdownConfirm}
        <button
          class="power-btn shutdown"
          onclick={() => (shutdownConfirm = true)}
          disabled={powerActionLoading !== null}
          title="Detiene todos los servicios excepto la API y la base de datos"
        >
          <DynamicIcon name="Power" size={12} /> Apagar
        </button>
      {:else}
        <button
          class="power-btn shutdown-confirm"
          onclick={shutdownServices}
          disabled={powerActionLoading !== null}
        >
          {#if powerActionLoading === 'shutdown'}
            <DynamicIcon name="LoaderCircle" size={12} /> Apagando…
          {:else}
            <DynamicIcon name="TriangleAlert" size={12} /> Confirmar apagado
          {/if}
        </button>
        <button
          class="power-btn cancel"
          onclick={() => (shutdownConfirm = false)}
          disabled={powerActionLoading !== null}
        >
          Cancelar
        </button>
      {/if}
    </div>

    <p class="hint">
      <strong>Hibernar</strong> detiene AI Service y Worker (la API y la base de datos siguen
      disponibles). <strong>Apagar</strong> detiene todo excepto la API y la base de datos — usa
      <span class="mono">joidy up</span> para reiniciar.
    </p>
  {/if}
</section>

<style>
  /* Restaurada: se perdió en el split #1067; el markup usaba la clase
     inválida ":global(hint)" que nunca matcheaba. */
  .hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.6;
    margin-top: 8px;
  }

  .section {
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-light);
  }

  .section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 12px;
  }

  /* ── Power management ──────────────────────────────────────────────────── */
  .power-service-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 10px;
  }

  .power-service-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 8px;
    border-radius: var(--r);
    background: var(--surface);
    font-size: 11px;
  }

  .power-service-name {
    color: var(--text-secondary);
    font-weight: 500;
  }

  .power-service-badge {
    font-size: 10px;
    font-family: var(--font-mono);
    letter-spacing: 0.02em;
  }

  .power-service-badge.running {
    color: var(--success);
  }

  .power-service-badge.stopped {
    color: var(--text-disabled);
  }

  .power-actions {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }

  .power-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 6px 12px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
    color: var(--text-secondary);
    font-size: 11px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast);
  }

  .power-btn:hover:not(:disabled) {
    background: var(--elevated);
    border-color: var(--text-muted);
    color: var(--text-primary);
  }

  .power-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .power-btn.sleep:hover:not(:disabled) {
    border-color: var(--info, var(--accent));
    color: var(--info, var(--accent));
  }

  .power-btn.wake:hover:not(:disabled) {
    border-color: var(--success);
    color: var(--success);
  }

  .power-btn.shutdown {
    border-color: color-mix(in srgb, var(--error) 40%, var(--border));
    color: var(--error);
  }

  .power-btn.shutdown:hover:not(:disabled) {
    background: color-mix(in srgb, var(--error) 10%, transparent);
    border-color: var(--error);
  }

  .power-btn.shutdown-confirm {
    background: var(--error);
    border-color: var(--error);
    color: white;
    font-weight: 600;
  }

  .power-btn.shutdown-confirm:hover:not(:disabled) {
    opacity: 0.9;
  }

  .power-btn.cancel {
    font-size: 10px;
    padding: 6px 10px;
  }
</style>
