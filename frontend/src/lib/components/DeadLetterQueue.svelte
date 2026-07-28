<script lang="ts">
  import { onMount } from 'svelte';
  import { api, type EmbeddingFailure } from '$lib/api';
  import Card from './Card.svelte';
  import DynamicIcon from './DynamicIcon.svelte';

  let failures = $state<EmbeddingFailure[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let purging = $state(false);

  onMount(() => load());

  async function load() {
    loading = true;
    error = null;
    try {
      failures = await api.embeddings.deadLetters();
    } catch (e) {
      error = 'No se pudieron cargar los embeddings fallidos.';
      failures = [];
    } finally {
      loading = false;
    }
  }

  async function reset(noteId: number) {
    try {
      await api.embeddings.resetDeadLetter(noteId);
      failures = failures.filter(f => f.note_id !== noteId);
    } catch {
      // notification already shown by api.ts
    }
  }

  async function purgeAll() {
    purging = true;
    try {
      await api.embeddings.purgeDeadLetters();
      failures = [];
    } catch {
      // notification already shown by api.ts
    } finally {
      purging = false;
    }
  }

  function formatDate(iso: string | null): string {
    if (!iso) return '—';
    const d = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 60000) return 'hace momentos';
    if (diff < 3600000) return `hace ${Math.floor(diff / 60000)} min`;
    if (diff < 86400000) return `hace ${Math.floor(diff / 3600000)} h`;
    return d.toLocaleDateString('es');
  }
</script>

<Card padding="md">
  <div class="dlq-header">
    <h3><DynamicIcon icon="AlertTriangle" /> Embeddings fallidos</h3>
    {#if failures.length > 0}
      <button class="btn-sm btn-danger" onclick={purgeAll} disabled={purging}>
        {purging ? 'Purgando...' : 'Purgar todos'}
      </button>
    {/if}
  </div>

  {#if loading}
    <p class="muted">Cargando...</p>
  {:else if error}
    <p class="muted">{error}</p>
  {:else if failures.length === 0}
    <p class="muted">No hay embeddings fallidos.</p>
  {:else}
    <div class="dlq-list">
      {#each failures as failure (failure.note_id)}
        <div class="dlq-item">
          <div class="dlq-info">
            <span class="dlq-title">{failure.note_title || `Nota #${failure.note_id}`}</span>
            <span class="dlq-meta">
              {failure.attempts} intentos · {formatDate(failure.updated_at)}
            </span>
            {#if failure.last_error}
              <span class="dlq-error">{failure.last_error}</span>
            {/if}
          </div>
          <button class="btn-sm" onclick={() => reset(failure.note_id)}>
            Reintentar
          </button>
        </div>
      {/each}
    </div>
  {/if}
</Card>

<style>
  .dlq-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  .dlq-header h3 {
    margin: 0;
    font-size: 1rem;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .muted {
    color: var(--color-muted, #888);
    font-size: 0.85rem;
    text-align: center;
    padding: 24px 0;
  }
  .dlq-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .dlq-item {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
    padding: 8px;
    border-radius: 6px;
    background: var(--color-surface, #f5f5f5);
  }
  .dlq-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .dlq-title {
    font-weight: 600;
    font-size: 0.875rem;
  }
  .dlq-meta {
    font-size: 0.75rem;
    color: var(--color-muted, #888);
  }
  .dlq-error {
    font-size: 0.75rem;
    color: var(--color-error, #e53e3e);
    font-family: monospace;
    word-break: break-word;
    max-height: 40px;
    overflow: hidden;
  }
  .btn-sm {
    padding: 4px 10px;
    font-size: 0.8rem;
    border: 1px solid var(--color-border, #ddd);
    border-radius: 4px;
    background: var(--color-bg, #fff);
    cursor: pointer;
    white-space: nowrap;
  }
  .btn-sm:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .btn-danger {
    color: var(--color-error, #e53e3e);
    border-color: var(--color-error, #e53e3e);
  }
</style>
