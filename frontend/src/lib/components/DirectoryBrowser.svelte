<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { createEventDispatcher } from 'svelte';
  import { Folder, ChevronRight, ArrowUp, Check, X, Loader2 } from 'lucide-svelte';
  import { api } from '$lib/api';
  import { logger } from '$lib/utils/logger';

  export let open = false;
  /** Title shown at the top of the modal. */
  export let title = 'Seleccionar carpeta';
  /** Starting path when the modal opens (e.g. "/vault"). */
  export let startPath = '/vault';
  /**
   * If set, the selected path is made relative to this base before being
   * dispatched. Used for `daily_notes_folder` (relative to the vault root).
   * If null, the absolute path is dispatched as-is.
   */
  export let relativeTo: string | null = null;

  const dispatch = createEventDispatcher<{ select: string; cancel: void }>();

  let currentPath = '';
  let parentPath: string | null = null;
  let entries: { name: string; path: string; is_dir: boolean }[] = [];
  let loading = false;
  let error = '';

  async function loadDir(path: string) {
    loading = true;
    error = '';
    try {
      const res = await api.config.browseDirs(path);
      currentPath = res.current;
      parentPath = res.parent;
      entries = res.entries;
    } catch (e: any) {
      error = e.message || 'Error al leer el directorio';
      entries = [];
    } finally {
      loading = false;
    }
  }

  $: if (open && currentPath === '') {
    loadDir(startPath);
  }

  function navigate(path: string) {
    loadDir(path);
  }

  function goUp() {
    if (parentPath) loadDir(parentPath);
  }

  function selectHere() {
    let result = currentPath;
    if (relativeTo && result.startsWith(relativeTo)) {
      result = result.slice(relativeTo.length).replace(/^\/+/, '');
    }
    dispatch('select', result);
    close();
  }

  function close() {
    dispatch('cancel');
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') close();
  }

  onMount(() => {
    window.addEventListener('keydown', onKeydown);
  });
  onDestroy(() => {
    window.removeEventListener('keydown', onKeydown);
  });

  // Reset state when modal closes so it re-opens fresh next time.
  $: if (!open) {
    currentPath = '';
    entries = [];
    error = '';
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="fp-backdrop" onclick={close}>
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div class="fp-modal" onclick={(e) => e.stopPropagation()}>
      <div class="fp-header">
        <span class="fp-title mono">{title}</span>
        <button class="fp-close" onclick={close} aria-label="Cerrar">
          <X size={14} />
        </button>
      </div>

      <!-- Breadcrumb / current path -->
      <div class="fp-path-bar">
        <button class="fp-up-btn" onclick={goUp} disabled={!parentPath} title="Subir">
          <ArrowUp size={13} />
        </button>
        <span class="fp-path mono" title={currentPath}>{currentPath}</span>
      </div>

      <!-- Directory listing -->
      <div class="fp-list">
        {#if loading}
          <div class="fp-empty">
            <Loader2 size={18} class="fp-spin" />
          </div>
        {:else if error}
          <div class="fp-empty fp-error">{error}</div>
        {:else if entries.length === 0}
          <div class="fp-empty">Sin subcarpetas.</div>
        {:else}
          {#each entries as entry (entry.path)}
            <button
              class="fp-item"
              onclick={() => navigate(entry.path)}
              ondblclick={selectHere}
            >
              <Folder size={15} />
              <span class="fp-item-name">{entry.name}</span>
              <ChevronRight size={13} class="fp-chevron" />
            </button>
          {/each}
        {/if}
      </div>

      <!-- Actions -->
      <div class="fp-actions">
        <button class="fp-btn fp-cancel" onclick={close}>Cancelar</button>
        <button class="fp-btn fp-select" onclick={selectHere}>
          <Check size={13} />
          Seleccionar esta carpeta
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .fp-backdrop {
    position: fixed; inset: 0; z-index: 1000;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(3px);
    display: flex; align-items: center; justify-content: center;
  }
  .fp-modal {
    background: var(--bg, #1a1a2e);
    border: 1px solid var(--border, #333);
    border-radius: 10px;
    width: 480px; max-width: 90vw;
    max-height: 70vh; display: flex; flex-direction: column;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  }
  .fp-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 16px; border-bottom: 1px solid var(--border-light, #222);
  }
  .fp-title { font-size: 13px; font-weight: 600; color: var(--text-primary); }
  .fp-close {
    background: none; border: none; cursor: pointer;
    color: var(--text-muted); padding: 4px; border-radius: 4px;
  }
  .fp-close:hover { background: var(--elevated); color: var(--text-primary); }

  .fp-path-bar {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 12px; border-bottom: 1px solid var(--border-light, #222);
  }
  .fp-up-btn {
    background: var(--elevated); border: 1px solid var(--border);
    border-radius: 4px; padding: 4px 6px; cursor: pointer;
    color: var(--text-secondary); display: flex; align-items: center;
  }
  .fp-up-btn:disabled { opacity: 0.3; cursor: not-allowed; }
  .fp-up-btn:not(:disabled):hover { color: var(--text-primary); }
  .fp-path {
    font-size: 11px; color: var(--text-muted);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1;
  }

  .fp-list {
    flex: 1; overflow-y: auto; padding: 4px 0;
    min-height: 180px; max-height: 320px;
  }
  .fp-item {
    display: flex; align-items: center; gap: 8px;
    width: 100%; padding: 8px 16px;
    background: none; border: none; cursor: pointer;
    color: var(--text-primary); font-size: 13px; text-align: left;
  }
  .fp-item:hover { background: var(--elevated); }
  .fp-item-name { flex: 1; }
  .fp-chevron { color: var(--text-muted); opacity: 0.4; }

  .fp-empty {
    padding: 32px; text-align: center; color: var(--text-muted);
    font-size: 13px; display: flex; align-items: center; justify-content: center;
  }
  .fp-error { color: var(--danger, #e74c3c); }
  .fp-spin { animation: fp-spin 1s linear infinite; }
  @keyframes fp-spin { to { transform: rotate(360deg); } }

  .fp-actions {
    display: flex; justify-content: flex-end; gap: 8px;
    padding: 10px 16px; border-top: 1px solid var(--border-light, #222);
  }
  .fp-btn {
    display: flex; align-items: center; gap: 6px;
    padding: 6px 14px; border-radius: 6px; font-size: 12px;
    cursor: pointer; border: 1px solid var(--border);
  }
  .fp-cancel {
    background: var(--elevated); color: var(--text-secondary);
  }
  .fp-cancel:hover { color: var(--text-primary); }
  .fp-select {
    background: var(--accent, #6366f1); color: white;
    border-color: var(--accent);
  }
  .fp-select:hover { opacity: 0.9; }
</style>
