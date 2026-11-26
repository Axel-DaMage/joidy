<script lang="ts">
  import { onMount } from 'svelte';
  import { api, type EmbeddingFailure } from '$lib/api';
  import Card from './Card.svelte';
  import { TriangleAlert } from 'lucide-svelte';
  import { getLocale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';

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
      failures = failures.filter((f) => f.note_id !== noteId);
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
    return d.toLocaleDateString(getLocale());
  }
</script>

<Card padding="md">
  <div class="dlq-header">
    <h3><TriangleAlert size={18} /> Embeddings fallidos</h3>
    {#if failures.length > 0}
      <button class="btn-sm btn-danger" onclick={purgeAll} disabled={purging}>
        {purging ? 'Purgando...' : 'Purgar todos'}
      </button>
    {/if}
  </div>

  {#if loading}
    <p class="muted">{$t('deadLetter.loading')}</p>
  {:else if error}
    <p class="muted">{error}</p>
  {:else if failures.length === 0}
    <p class="muted">{$t('deadLetter.noFailures')}</p>
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
          <button class="btn-sm" onclick={() => reset(failure.note_id)}> Reintentar </button>
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
    color: var(--text-muted, #888);
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
    background: var(--elevated, transparent);
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
    color: var(--text-muted, #888);
  }
  .dlq-error {
    font-size: 0.75rem;
    color: var(--error, #e53e3e);
    font-family: monospace;
    word-break: break-word;
    max-height: 40px;
    overflow: hidden;
  }
  .btn-sm {
    padding: 4px 10px;
    font-size: 0.8rem;
    border: 1px solid var(--border, #ddd);
    border-radius: 4px;
    background: var(--surface, transparent);
    color: var(--text-primary, inherit);
    cursor: pointer;
    white-space: nowrap;
  }
  .btn-sm:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .btn-danger {
    color: var(--error, #e53e3e);
    border-color: var(--error, #e53e3e);
  }
</style>
