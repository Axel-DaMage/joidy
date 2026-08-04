<script lang="ts">
  import { syncStore, type SyncConflict, type ConflictResolution } from '$lib/stores/sync';
  import ModalDialog from './ModalDialog.svelte';
  import { AlertTriangle, FileText, Upload, Download, GitMerge } from 'lucide-svelte';

  let selectedConflict: SyncConflict | null = null;
  let resolution: ConflictResolution | null = null;
  let mergedContent = '';
  let resolving = false;

  // Auto-open modal only for conflicts the user hasn't dismissed this session.
  // The dismissed set lives in the syncStore so it persists across navigations
  // (component is recreated on each route change, local state would be lost).
  $: {
    const undismissed = $syncStore.conflicts.filter(c => !$syncStore.dismissed.has(c.note_id));
    if (undismissed.length > 0 && !selectedConflict) {
      selectedConflict = undismissed[0];
      resolution = null;
      mergedContent = '';
    }
  }

  $: if ($syncStore.conflicts.length === 0) {
    selectedConflict = null;
  }

  async function handleResolve() {
    if (!selectedConflict || !resolution) return;
    resolving = true;
    const ok = await syncStore.resolveConflict(
      selectedConflict.note_id,
      resolution,
      resolution === 'merge' ? mergedContent : undefined
    );
    resolving = false;
    if (ok) {
      selectedConflict = null;
      resolution = null;
      mergedContent = '';
    }
  }

  function handleSkip() {
    if (selectedConflict) {
      syncStore.dismissConflict(selectedConflict.note_id);
    }
    selectedConflict = null;
    resolution = null;
    mergedContent = '';
  }
</script>

{#if selectedConflict}
  <ModalDialog
    open={true}
    title="Conflicto de Sincronización"
    size="lg"
    onClose={handleSkip}
  >
    <div class="conflict-info">
      <div class="conflict-icon">
        <AlertTriangle size={24} color="var(--warning)" />
      </div>
      <p class="conflict-desc">
        Se detectaron cambios simultáneos en <strong>{selectedConflict.title}</strong>
        desde Joidy y Obsidian. Elige cómo resolver el conflicto.
      </p>
    </div>

    <div class="conflict-meta">
      <div class="meta-item">
        <span class="meta-label">Archivo</span>
        <span class="meta-value">{selectedConflict.source_path}</span>
      </div>
      <div class="meta-row">
        <div class="meta-item">
          <span class="meta-label">Local (Joidy)</span>
          <span class="meta-value">{selectedConflict.local_mtime ?? '—'}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Remoto (Obsidian)</span>
          <span class="meta-value">{selectedConflict.remote_mtime ?? '—'}</span>
        </div>
      </div>
    </div>

    <div class="resolution-options">
      <button
        class="resolution-btn"
        class:active={resolution === 'keep_local'}
        onclick={() => resolution = 'keep_local'}
      >
        <FileText size={18} />
        <div class="resolution-text">
          <span class="resolution-title">Mantener Local</span>
          <span class="resolution-desc">Descartar cambios de Obsidian, conservar Joidy</span>
        </div>
      </button>

      <button
        class="resolution-btn"
        class:active={resolution === 'keep_remote'}
        onclick={() => resolution = 'keep_remote'}
      >
        <Download size={18} />
        <div class="resolution-text">
          <span class="resolution-title">Mantener Remoto</span>
          <span class="resolution-desc">Sobrescribir Joidy con el contenido de Obsidian</span>
        </div>
      </button>

      <button
        class="resolution-btn"
        class:active={resolution === 'merge'}
        onclick={() => resolution = 'merge'}
      >
        <GitMerge size={18} />
        <div class="resolution-text">
          <span class="resolution-title">Fusionar Manualmente</span>
          <span class="resolution-desc">Editar el contenido combinado</span>
        </div>
      </button>
    </div>

    {#if resolution === 'merge'}
      <div class="merge-editor">
        <label class="label">Contenido fusionado</label>
        <textarea
          class="input w-full"
          bind:value={mergedContent}
          rows="10"
          placeholder="Pega o edita el contenido combinado aquí..."
        ></textarea>
      </div>
    {/if}

    {#if $syncStore.conflicts.length > 1}
      <p class="more-conflicts">
        {$syncStore.conflicts.length - 1} conflicto(s) más pendiente(s)
      </p>
    {/if}

    {#snippet footer()}
      <button class="btn btn-ghost" onclick={handleSkip}>Saltar</button>
      <button
        class="btn btn-primary"
        onclick={handleResolve}
        disabled={!resolution || resolving || (resolution === 'merge' && !mergedContent.trim())}
      >
        {resolving ? 'Resolviendo...' : 'Resolver'}
      </button>
    {/snippet}
  </ModalDialog>
{/if}

<style>
  .conflict-info {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 16px;
  }

  .conflict-icon {
    flex-shrink: 0;
    padding: 8px;
    background: color-mix(in srgb, var(--warning) 10%, transparent);
    border-radius: var(--r);
  }

  .conflict-desc {
    margin: 0;
    font-size: 14px;
    color: var(--text-primary);
    line-height: 1.5;
  }

  .conflict-meta {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 12px;
    margin-bottom: 16px;
  }

  .meta-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .meta-row {
    display: flex;
    gap: 20px;
    margin-top: 8px;
  }

  .meta-label {
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .meta-value {
    font-size: 13px;
    color: var(--text-primary);
    font-family: var(--font-mono);
    word-break: break-all;
  }

  .resolution-options {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 16px;
  }

  .resolution-btn {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    cursor: pointer;
    text-align: left;
    transition: all 0.15s ease;
    color: var(--text-primary);
  }

  .resolution-btn:hover {
    border-color: var(--accent);
    background: var(--hover);
  }

  .resolution-btn.active {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
    background: color-mix(in srgb, var(--accent) 5%, transparent);
  }

  .resolution-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .resolution-title {
    font-size: 14px;
    font-weight: 600;
  }

  .resolution-desc {
    font-size: 12px;
    color: var(--text-muted);
  }

  .merge-editor {
    margin-bottom: 16px;
  }

  .merge-editor textarea {
    font-family: var(--font-mono);
    font-size: 13px;
    resize: vertical;
  }

  .more-conflicts {
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
    margin: 0;
  }
</style>
