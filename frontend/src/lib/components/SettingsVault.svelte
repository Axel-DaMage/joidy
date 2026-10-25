<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';
  import { writeInObsidian } from '$lib/stores/settings';
  import type { SystemConfig } from '$lib/utils/settingsTypes';

  interface Props {
    systemConfig: SystemConfig;
    isConfigured: (key: string) => boolean;
  }

  let { systemConfig = $bindable(), isConfigured }: Props = $props();
</script>

<!-- Vault -->
<section class="section">
  <div class="section-title" style="color: var(--xp, var(--accent));">
    <DynamicIcon name="Database" size={12} /> Obsidian Vault
  </div>
  <div class="row" style="flex-direction: column; align-items: stretch; gap: 8px;">
    <div class="row-label">
      <span>Directorio del Vault</span>
      {#if isConfigured('obsidian_vault_path')}<span class="configured-badge">✓</span>{/if}
    </div>
    <div
      style="display: flex; align-items: center; gap: 2px; padding: 0 10px; background: var(--elevated); border: 1px solid var(--border); border-radius: var(--r);"
      class="input-wrapper"
    >
      <input
        type="text"
        class="setting-input mono"
        style="border: none; background: transparent; flex: 1; padding-left: 2px;"
        placeholder="~/Documentos/notas/mi-vault"
        bind:value={systemConfig.obsidian_vault_path}
      />
    </div>
    <p class="hint">
      Ruta a tu vault desde tu <code>home</code>. Ej:
      <code>~/Documentos/notas/mi-vault</code>. Al guardar, <code>joidy up</code> expande
      <code>~</code> automáticamente.
    </p>
  </div>
  <div class="row" style="flex-direction: column; align-items: stretch; gap: 8px;">
    <div class="row-label">
      <span>Carpeta de notas diarias</span>
      {#if isConfigured('daily_notes_folder')}<span class="configured-badge">✓</span>{/if}
    </div>
    <div
      style="display: flex; align-items: center; gap: 2px; padding: 0 10px; background: var(--elevated); border: 1px solid var(--border); border-radius: var(--r);"
      class="input-wrapper"
    >
      <span class="mono" style="color: var(--text-disabled); font-size: 11px;">~</span>
      <input
        type="text"
        class="setting-input mono"
        style="border: none; background: transparent; flex: 1; padding-left: 2px;"
        placeholder="Ejemplo/Daily"
        bind:value={systemConfig.daily_notes_folder}
      />
    </div>
  </div>
  <div class="row">
    <div class="row-label">
      <DynamicIcon name="FolderRoot" size={13} />
      <span>Escribir en Vault nativo</span>
    </div>
    <button class="toggle" onclick={() => writeInObsidian.toggle()}>
      <span class:active={!$writeInObsidian}>aislado</span>
      <span class="sep">/</span>
      <span class:active={$writeInObsidian}>nativo</span>
    </button>
  </div>
  <p class="hint">
    {#if !$writeInObsidian}
      Joidy escribe en <code>_joidy/</code>. No modifica notas nativas.
    {:else}
      Joidy creará las notas directamente en la raíz de tu Vault.
    {/if}
  </p>
</section>

<style>
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

  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 0;
  }

  .row-label {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 12px;
    color: var(--text-secondary);
  }

  .hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.6;
    margin-top: 8px;
  }
  .hint code {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-secondary);
    background: var(--elevated);
    padding: 1px 4px;
    border-radius: 2px;
  }

  .toggle {
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 3px 8px;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
    transition: border-color var(--t-fast);
  }
  .toggle:hover {
    border-color: var(--text-muted);
  }
  .toggle .active {
    color: var(--text-primary);
  }
  .toggle .sep,
  .setting-input {
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 6px 10px;
    font-size: 11px;
    color: var(--text-primary);
    outline: none;
    transition: border-color var(--t-fast);
    width: 100%;
  }
  .setting-input:focus {
    outline: none;
  }

  .input-wrapper:focus-within {
    border-color: var(--text-muted);
  }

  .configured-badge {
    font-size: 10px;
    color: var(--success);
    margin-left: 4px;
  }
</style>
