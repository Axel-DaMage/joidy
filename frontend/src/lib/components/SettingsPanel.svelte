<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import { accentColors, activeIconPack, showFrontmatter, showTrash, showHiddenFiles, writeInObsidian, use24HourClock, hideTagsLine, type IconPack, MAX_COLORS } from '$lib/stores/settings';

  export let open = false;

  const dispatch = createEventDispatcher<{ close: void }>();

  let theme: 'dark' | 'light' = 'dark';

  const ICON_PACKS: { value: IconPack, label: string }[] = [
    { value: 'lucide', label: 'Lucide (Por Defecto)' },
    { value: 'phosphor', label: 'Phosphor' },
    { value: 'material', label: 'Material' }
  ];

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

  let offsetPx = 0;
  let isDragging = false;
  let startX = 0;
  let baseColors: string[] = [];

  function getFloatedColors(): string[] {
    if (baseColors.length < 2) return $accentColors;
    const n = baseColors.length;
    const pxPerColor = 120;
    const fullShift = offsetPx / pxPerColor;
    const result: string[] = [];
    for (let i = 0; i < n; i++) {
      const targetIdx = i + fullShift;
      const lo = Math.floor(targetIdx);
      const hi = lo + 1;
      const t = targetIdx - lo;
      const loIdx = ((lo % n) + n) % n;
      const hiIdx = ((hi % n) + n) % n;
      result.push(lerp(baseColors[loIdx], baseColors[hiIdx], t));
    }
    return result;
  }

  function lerp(c1: string, c2: string, t: number): string {
    const r1 = parseInt(c1.slice(1,3), 16);
    const g1 = parseInt(c1.slice(3,5), 16);
    const b1 = parseInt(c1.slice(5,7), 16);
    const r2 = parseInt(c2.slice(1,3), 16);
    const g2 = parseInt(c2.slice(3,5), 16);
    const b2 = parseInt(c2.slice(5,7), 16);
    const r = Math.round(r1 + (r2 - r1) * t);
    const g = Math.round(g1 + (g2 - g1) * t);
    const b = Math.round(b1 + (b2 - b1) * t);
    return `#${r.toString(16).padStart(2,'0')}${g.toString(16).padStart(2,'0')}${b.toString(16).padStart(2,'0')}`;
  }

  function onGradientMouseDown(e: MouseEvent) {
    isDragging = true;
    startX = e.clientX;
    baseColors = [...$accentColors];
    window.addEventListener('mousemove', onGradientMouseMove);
    window.addEventListener('mouseup', onGradientMouseUp);
  }

  function onGradientMouseMove(e: MouseEvent) {
    if (!isDragging) return;
    offsetPx = e.clientX - startX;
  }

  function onGradientMouseUp() {
    isDragging = false;
    const pxPerColor = 120;
    const steps = Math.round(offsetPx / pxPerColor);
    if (steps !== 0 && baseColors.length > 0) {
      const n = baseColors.length;
      const rotated: string[] = [];
      for (let i = 0; i < n; i++) {
        rotated.push(baseColors[(i + steps) % n]);
      }
      rotated.forEach((c, i) => accentColors.setColor(i, c));
    }
    offsetPx = 0;
    baseColors = [];
    window.removeEventListener('mousemove', onGradientMouseMove);
    window.removeEventListener('mouseup', onGradientMouseUp);
  }

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
        <button class="close-btn" on:click={close}><DynamicIcon name="X" size={14} /></button>
      </div>

      <div class="panel-body">

        <!-- Apariencia -->
        <section class="section">
          <div class="section-title" style="color: var(--xp, var(--accent));">Apariencia</div>
          <div class="row">
            <div class="row-label">
              {#if theme === 'dark'}<DynamicIcon name="Moon" size={13} />{:else}<DynamicIcon name="Sun" size={13} />{/if}
              <span>Tema</span>
            </div>
            <button class="toggle" on:click={toggleTheme}>
              <span class:active={theme === 'dark'}>oscuro</span>
              <span class="sep">/</span>
              <span class:active={theme === 'light'}>claro</span>
            </button>
          </div>

          <div class="row">
            <div class="row-label">
              <DynamicIcon name="Clock3" size={13} />
              <span>Formato de hora</span>
            </div>
            <button class="toggle" on:click={() => use24HourClock.toggle()}>
              <span class:active={$use24HourClock}>24h</span>
              <span class="sep">/</span>
              <span class:active={!$use24HourClock}>12h</span>
            </button>
          </div>

          <!-- Gradient preview bar -->
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div 
            class="gradient-preview" 
            style="background: {gradientPreview}; cursor: grab;"
            on:mousedown={onGradientMouseDown}
            class:dragging={isDragging}
          ></div>
          <p class="color-limit-note mono">Máximo {MAX_COLORS} colores</p>

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
                    <DynamicIcon name="Minus" size={10} />
                  </button>
                {/if}
              </div>
            {/each}
          </div>

          {#if $accentColors.length < MAX_COLORS}
            <button class="add-color-btn mono" on:click={() => accentColors.addColor()}>
              <DynamicIcon name="Plus" size={10} /> agregar color
            </button>
          {/if}

          <!-- Icon Packs Selector -->
          <div class="row" style="margin-top: 16px; flex-direction: column; align-items: stretch; gap: 8px;">
            <div class="row-label"><span>Set de Iconos (Alternativa Emojis)</span></div>
            <select class="setting-input mono" bind:value={$activeIconPack}>
              {#each ICON_PACKS as pack}
                <option value={pack.value}>{pack.label}</option>
              {/each}
            </select>
            <p class="hint" style="margin-top: 2px;">Los iconos cambiarán en los conectores y notas.</p>
          </div>
        </section>

        <!-- Vault -->
        <section class="section">
          <div class="section-title" style="color: var(--xp, var(--accent));">
            <DynamicIcon name="Database" size={12} /> Obsidian Vault
          </div>
          <div class="row" style="flex-direction: column; align-items: stretch; gap: 8px;">
            <div class="row-label"><span>Directorio del Vault (relativo a tilde ~)</span></div>
            <div style="display: flex; align-items: center; gap: 2px; padding: 0 10px; background: var(--elevated); border: 1px solid var(--border); border-radius: var(--r); transition: border-color var(--t-fast);" class="input-wrapper">
              <span class="mono" style="color: var(--text-disabled); font-size: 11px;">~</span>
              <input type="text" class="setting-input mono" style="border: none; background: transparent; flex: 1; padding-left: 2px;" placeholder="/Documentos/ObsidianVault" />
            </div>
          </div>
          <div class="row">
            <div class="row-label"><span>Carpeta Joidy</span></div>
            <code class="path-value">_joidy/</code>
          </div>
          <div class="row">
            <div class="row-label">
              <DynamicIcon name="FolderRoot" size={13} />
              <span>Escribir en Vault nativo</span>
            </div>
            <button class="toggle" on:click={() => writeInObsidian.toggle()}>
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

        <!-- Integraciones -->
        <section class="section">
          <div class="section-title" style="color: var(--xp, var(--accent));">
            <DynamicIcon name="GitBranch" size={12} /> Integraciones
          </div>
          <div class="row" style="flex-direction: column; align-items: stretch; gap: 8px;">
            <div class="row-label"><span>GitHub Token</span></div>
            <input type="text" class="setting-input mono" placeholder="ghp_..." />
          </div>
          <div class="row" style="flex-direction: column; align-items: stretch; gap: 8px;">
            <div class="row-label"><span>Telegram Bot</span></div>
            <input type="text" class="setting-input mono" placeholder="123456:ABC..." />
          </div>
        </section>

        <!-- IA -->
        <section class="section">
          <div class="section-title" style="color: var(--xp, var(--accent));">
            <DynamicIcon name="Zap" size={12} /> IA
          </div>
          <div class="row" style="flex-direction: column; align-items: stretch; gap: 8px;">
            <div class="row-label"><span>Gemini API Key</span></div>
            <input type="text" class="setting-input mono" placeholder="AIzaSy..." />
          </div>
          <p class="hint">
            Habilita auto-tagging y búsqueda semántica.
          </p>
        </section>

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
            <button class="toggle" on:click={() => showFrontmatter.toggle()}>
              <span class:active={!$showFrontmatter}>oculto</span>
              <span class="sep">/</span>
              <span class:active={$showFrontmatter}>visible</span>
            </button>
          </div>

          <div class="row">
            <div class="row-label">
              <DynamicIcon name="EyeOff" size={13} />
              <span>Carpetas Ocultas ( .folder )</span>
            </div>
            <button class="toggle" on:click={() => showHiddenFiles.toggle()}>
              <span class:active={!$showHiddenFiles}>oculto</span>
              <span class="sep">/</span>
              <span class:active={$showHiddenFiles}>visible</span>
            </button>
          </div>

          <div class="row">
            <div class="row-label">
              <DynamicIcon name="Trash2" size={13} />
              <span>Papelera Obsidian (.trash)</span>
            </div>
            <button class="toggle" on:click={() => showTrash.toggle()}>
              <span class:active={!$showTrash}>oculto</span>
              <span class="sep">/</span>
              <span class:active={$showTrash}>visible</span>
            </button>
          </div>

          <div class="row">
            <div class="row-label">
              <DynamicIcon name="Tag" size={13} />
              <span>Ocultar línea # Tags</span>
            </div>
            <button class="toggle" on:click={() => hideTagsLine.toggle()}>
              <span class:active={$hideTagsLine}>sí</span>
              <span class="sep">/</span>
              <span class:active={!$hideTagsLine}>no</span>
            </button>
          </div>
        </section>

        <!-- Info -->
        <section class="section" style="border-bottom: none;">
          <div class="row">
            <div class="row-label"><span>Versión</span></div>
            <span class="mono" style="font-size:11px; color: var(--xp, var(--accent));">v0.1.0</span>
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
    height: 24px;
    border-radius: 4px;
    margin: 8px 0 10px;
    transition: background 300ms ease;
    overflow-x: auto;
    overflow-y: hidden;
    white-space: nowrap;
    scrollbar-width: thin;
    scrollbar-color: var(--text-disabled) transparent;
  }

  .gradient-preview::-webkit-scrollbar {
    height: 4px;
  }

  .gradient-preview::-webkit-scrollbar-track {
    background: transparent;
  }

  .gradient-preview::-webkit-scrollbar-thumb {
    background: var(--text-disabled);
    border-radius: 2px;
  }

  .gradient-preview.dragging {
    cursor: grabbing;
  }

  .color-limit-note {
    margin: -4px 0 10px;
    font-size: 10px;
    color: var(--text-disabled);
    letter-spacing: 0.04em;
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
  .setting-input:focus { outline: none; }
  
  .input-wrapper:focus-within {
    border-color: var(--text-muted) !important;
  }

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
  .add-color-btn:focus-visible {
    outline: none;
    border-color: var(--xp);
    color: var(--xp);
  }
</style>
