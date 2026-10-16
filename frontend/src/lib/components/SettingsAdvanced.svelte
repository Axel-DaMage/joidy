<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';
  import { showFrontmatter, showTrash, showHiddenFiles, hideTagsLine } from '$lib/stores/settings';
</script>

<!-- Avanzado -->
<section class="section">
  <div class="section-title" style="color: var(--xp, var(--accent));">
    <DynamicIcon name="Settings" size={12} /> Avanzado
  </div>

  <div class="row">
    <div class="row-label">
      <DynamicIcon name="Code" size={13} />
      <span>Metadatos (YAML)</span>
    </div>
    <button class="toggle" onclick={() => showFrontmatter.toggle()}>
      <span class:active={!$showFrontmatter}>oculto</span>
      <span class="sep">/</span>
      <span class:active={$showFrontmatter}>visible</span>
    </button>
  </div>

  <div class="row">
    <div class="row-label">
      <DynamicIcon name="EyeOff" size={13} />
      <span>Carpetas Ocultas</span>
    </div>
    <button class="toggle" onclick={() => showHiddenFiles.toggle()}>
      <span class:active={!$showHiddenFiles}>oculto</span>
      <span class="sep">/</span>
      <span class:active={$showHiddenFiles}>visible</span>
    </button>
  </div>

  <div class="row">
    <div class="row-label">
      <DynamicIcon name="Trash2" size={13} />
      <span>Mostrar Papelera</span>
    </div>
    <button class="toggle" onclick={() => showTrash.toggle()}>
      <span class:active={!$showTrash}>oculto</span>
      <span class="sep">/</span>
      <span class:active={$showTrash}>visible</span>
    </button>
  </div>

  <div class="row">
    <div class="row-label">
      <DynamicIcon name="Tag" size={13} />
      <span>Línea de Etiquetas</span>
    </div>
    <button class="toggle" onclick={() => hideTagsLine.toggle()}>
      <span class:active={$hideTagsLine}>oculta</span>
      <span class="sep">/</span>
      <span class:active={!$hideTagsLine}>visible</span>
    </button>
  </div>
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
  .toggle .sep {
    background: var(--accent);
    color: white;
    border: none;
    padding: 6px 12px;
    border-radius: var(--r);
    font-size: 11px;
    cursor: pointer;
    font-family: var(--font-mono);
  }
</style>
