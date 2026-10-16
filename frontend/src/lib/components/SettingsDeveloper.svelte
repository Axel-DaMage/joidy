<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';
  import { devMode } from '$lib/stores/settings';
</script>

<!-- Repositorio -->
<section class="section">
  <div class="row">
    <div class="row-label"><span>Repositorio</span></div>
    <a
      href="https://github.com/Axel-DaMage/joidy"
      target="_blank"
      rel="noopener"
      class="mono"
      style="font-size:11px; color: var(--text-secondary);">github.com/Axel-DaMage/joidy</a
    >
  </div>
</section>

<!-- Desarrollador -->
<section class="section">
  <div class="section-title" style="color: var(--xp, var(--accent));">
    <DynamicIcon name="Code" size={12} /> Desarrollador
  </div>
  <div class="row">
    <div class="row-label">
      <DynamicIcon name="Wrench" size={13} />
      <span>Modo Desarrollo</span>
    </div>
    <button class="toggle" onclick={() => devMode.toggle()}>
      <span class:active={!$devMode}>off</span>
      <span class="sep">/</span>
      <span class:active={$devMode}>on</span>
    </button>
  </div>
  <p class="hint">Activa para mostrar contenido avanzado e integraciones experimentales.</p>
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
