<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { X, Moon, Sun, Database, GitBranch, Zap, Palette, Plus, Minus } from 'lucide-svelte';
  import { accentColors, MAX_COLORS } from '$lib/stores/settings';

  export let open = false;

  const dispatch = createEventDispatcher<{ close: void }>();

  let theme: 'dark' | 'light' = 'dark';

  function toggleTheme() {
    theme = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', theme === 'light' ? 'light' : 'dark');
  }

  function onColorPicker(i: number, e: Event) {
    accentColors.setColor(i, (e.target as HTMLInputElement).value);
  }

  function onHex(i: number, e: Event) {
    const raw = (e.target as HTMLInputElement).value.trim();
    const full = raw.startsWith('#') ? raw : '#' + raw;
    if (/^#[0-9a-fA-F]{6}$/.test(full)) accentColors.setColor(i, full);
  }

  $: gradientPreview = $accentColors.length === 1
    ? $accentColors[0]
    : `linear-gradient(to right, ${$accentColors.join(', ')})`;

  function close() {
    dispatch('close');
  }

  function onBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) close();
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') close();
  }
</script>

<svelte:window on:keydown={onKeydown} />

{#if open}
  <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
  <div class="backdrop" on:click={onBackdropClick}>
    <div class="panel">
      <div class="panel-header">
        <span class="mono" style="font-size:12px; letter-spacing:0.08em;">AJUSTES</span>
        <button class="close-btn" on:click={close}><X size={14} /></button>
      </div>

      <div class="panel-body">

        <!-- Apariencia -->
        <section class="section">
          <div class="section-title">Apariencia</div>
          <div class="row">
            <div class="row-label">
              {#if theme === 'dark'}<Moon size={13} />{:else}<Sun size={13} />{/if}
              <span>Tema</span>
            </div>
            <button class="toggle" on:click={toggleTheme}>
              <span class:active={theme === 'dark'}>oscuro</span>
              <span class="sep">/</span>
              <span class:active={theme === 'light'}>claro</span>
            </button>
          </div>
          <!-- Gradient preview bar -->
          <div class="gradient-preview" style="background: {gradientPreview};"></div>

          <!-- Per-color rows -->
          <div class="color-list">
            {#each $accentColors as color, i}
              <div class="color-entry">
                <span class="color-idx mono">{i + 1}</span>
                <input
                  type="color"
                  class="color-swatch"
                  value={color}
                  on:input={(e) => onColorPicker(i, e)}
                />
                <input
                  type="text"
                  class="hex-input mono"
                  maxlength="7"
                  value={color}
                  on:input={(e) => onHex(i, e)}
                  placeholder="#c8a96e"
                />
                {#if $accentColors.length > 1}
                  <button class="color-rm" on:click={() => accentColors.removeColor(i)} title="Quitar">
                    <Minus size={10} />
                  </button>
                {/if}
              </div>
            {/each}
          </div>

          {#if $accentColors.length < MAX_COLORS}
            <button class="add-color-btn mono" on:click={() => accentColors.addColor()}>
              <Plus size={10} /> agregar color
            </button>
          {/if}
        </section>

        <!-- Vault -->
        <section class="section">
          <div class="section-title">
            <Database size={12} /> Obsidian Vault
          </div>
          <div class="row">
            <div class="row-label"><span>Ruta actual</span></div>
            <code class="path-value">…/Sincronizacion</code>
          </div>
          <div class="row">
            <div class="row-label"><span>Carpeta Joidy</span></div>
            <code class="path-value">_joidy/</code>
          </div>
          <p class="hint">
            Joidy escribe en <code>_joidy/</code> exclusivamente.<br>
            Nunca modifica tus notas de Obsidian.
          </p>
        </section>

        <!-- Integraciones -->
        <section class="section">
          <div class="section-title">
            <GitBranch size={12} /> Integraciones
          </div>
          <div class="row">
            <div class="row-label"><span>GitHub Token</span></div>
            <span class="badge badge-off">no configurado</span>
          </div>
          <div class="row">
            <div class="row-label"><span>Telegram Bot</span></div>
            <span class="badge badge-off">no configurado</span>
          </div>
          <p class="hint">Configura en el archivo <code>.env</code> del proyecto.</p>
        </section>

        <!-- IA -->
        <section class="section">
          <div class="section-title">
            <Zap size={12} /> IA
          </div>
          <div class="row">
            <div class="row-label"><span>Gemini API</span></div>
            <span class="badge badge-off">deshabilitada</span>
          </div>
          <p class="hint">
            Agrega <code>GEMINI_API_KEY</code> en <code>.env</code> y reinicia para habilitar
            auto-tagging y búsqueda semántica.
          </p>
        </section>

        <!-- Info -->
        <section class="section" style="border-bottom: none;">
          <div class="row">
            <div class="row-label"><span>Versión</span></div>
            <span class="mono" style="font-size:11px; color: var(--text-muted);">v0.1.0</span>
          </div>
          <div class="row">
            <div class="row-label"><span>Repositorio</span></div>
            <a
              href="https://github.com/Axel-DaMage/joidy"
              target="_blank"
              rel="noopener"
              class="mono"
              style="font-size:11px; color: var(--text-secondary);"
            >github.com/Axel-DaMage/joidy</a>
          </div>
        </section>

      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    z-index: 100;
    display: flex;
    align-items: flex-start;
    justify-content: flex-end;
  }

  .panel {
    width: 340px;
    height: 100%;
    background: var(--surface);
    border-left: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    animation: slideIn 150ms ease-out;
  }

  @keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to   { transform: translateX(0);    opacity: 1; }
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 20px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .close-btn {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 4px;
    display: flex;
    align-items: center;
    border-radius: var(--r);
    transition: color var(--t-fast);
  }
  .close-btn:hover { color: var(--text-primary); }

  .panel-body {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
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
    gap: 4px;
    transition: border-color var(--t-fast);
  }
  .toggle:hover { border-color: var(--text-muted); }
  .toggle .active { color: var(--text-primary); }
  .toggle .sep { color: var(--border); }

  .badge {
    font-size: 10px;
    font-family: var(--font-mono);
    padding: 2px 7px;
    border-radius: 2px;
    letter-spacing: 0.05em;
  }
  .badge-off {
    background: var(--elevated);
    color: var(--text-muted);
    border: 1px solid var(--border);
  }

  .path-value {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-secondary);
    background: var(--elevated);
    padding: 2px 6px;
    border-radius: 2px;
    max-width: 160px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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

  /* ── Accent gradient builder ── */
  .gradient-preview {
    height: 6px;
    border-radius: 3px;
    margin: 8px 0 10px;
    transition: background 300ms ease;
  }

  .color-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .color-entry {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .color-idx {
    font-size: 9px;
    color: var(--text-disabled);
    width: 10px;
    text-align: right;
  }

  .color-swatch {
    width: 26px;
    height: 26px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: none;
    cursor: pointer;
    padding: 2px;
    flex-shrink: 0;
  }

  .hex-input {
    flex: 1;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 4px 7px;
    font-size: 11px;
    color: var(--text-primary);
    outline: none;
    transition: border-color var(--t-fast);
  }
  .hex-input:focus { border-color: var(--text-muted); }

  .color-rm {
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    flex-shrink: 0;
    transition: color var(--t-fast), border-color var(--t-fast);
  }
  .color-rm:hover { color: var(--error); border-color: var(--error); }

  .add-color-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 8px;
    background: none;
    border: 1px dashed var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    font-size: 10px;
    padding: 4px 10px;
    cursor: pointer;
    width: 100%;
    justify-content: center;
    transition: color var(--t-fast), border-color var(--t-fast);
  }
  .add-color-btn:hover { color: var(--text-secondary); border-color: var(--text-muted); }
</style>
