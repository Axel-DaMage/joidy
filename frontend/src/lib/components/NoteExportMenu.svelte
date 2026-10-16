<script lang="ts">
  import { Download } from 'lucide-svelte';
  import type { Note } from '$lib/api';
  import { downloadMarkdown, downloadHTML, copyNoteAsMarkdown } from '$lib/utils/export';
  import { showNotification } from '$lib/stores/gamification';

  let { note }: { note: Note } = $props();

  let showExportMenu = $state(false);
</script>

<div
  style="position: relative; display: inline-block; z-index: {showExportMenu
    ? 'var(--z-overlay)'
    : 'auto'};"
>
  <button
    class="toolbar-btn"
    class:active={showExportMenu}
    style="position: relative; z-index: var(--z-overlay);"
    onclick={() => (showExportMenu = !showExportMenu)}
    title="Exportar nota"
  >
    <Download size={14} />
    <span>Exportar</span>
  </button>

  {#if showExportMenu}
    <!-- Backdrop to close dropdown on outside click -->
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div
      style="position: fixed; inset: 0; z-index: var(--z-dropdown); cursor: default;"
      onclick={() => (showExportMenu = false)}
      role="presentation"
      tabindex="-1"
    ></div>

    <div class="export-dropdown-menu">
      <button
        class="dropdown-item"
        onclick={() => {
          downloadMarkdown(note);
          showExportMenu = false;
        }}
      >
        <span class="dropdown-icon">⬡</span>
        <span>Descargar Markdown</span>
      </button>
      <button
        class="dropdown-item"
        onclick={() => {
          downloadHTML(note);
          showExportMenu = false;
        }}
      >
        <span class="dropdown-icon">◆</span>
        <span>Descargar HTML</span>
      </button>
      <button
        class="dropdown-item"
        onclick={async () => {
          if (note) {
            const ok = await copyNoteAsMarkdown(note);
            if (ok) showNotification('¡Nota copiada al portapapeles!', 'success');
          }
          showExportMenu = false;
        }}
      >
        <span class="dropdown-icon">⚡</span>
        <span>Copiar Markdown</span>
      </button>
    </div>
  {/if}
</div>

<style>
  /* ── Export Dropdown ── */
  .export-dropdown-menu {
    position: absolute;
    top: calc(100% + 4px);
    right: 0;
    width: 180px;
    background: var(--surface);
    backdrop-filter: blur(10px);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 4px;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
    z-index: var(--z-modal);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .dropdown-item {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 6px 10px;
    background: transparent;
    border: none;
    border-radius: var(--r-sm, 4px);
    color: var(--text-secondary);
    font-size: 11px;
    text-align: left;
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .dropdown-item:hover {
    background: var(--elevated);
    color: var(--text-primary);
  }
  .dropdown-icon {
    font-size: 12px;
    color: var(--xp);
    width: 14px;
    text-align: center;
  }

  .toolbar-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 7px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: transparent;
    color: var(--text-secondary);
    font-size: 10px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast);
    white-space: nowrap;
  }

  .toolbar-btn:hover {
    background: var(--elevated);
    color: var(--text-primary);
  }
  .toolbar-btn.active {
    border-color: var(--text-secondary);
    color: var(--text-primary);
  }
</style>
