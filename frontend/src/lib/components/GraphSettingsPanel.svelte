<script lang="ts">
  import { t } from 'svelte-i18n';

  interface ColorGroup {
    query: string;
    color: string;
  }

  interface Props {
    searchQuery: string;
    showNotes: boolean;
    showTags: boolean;
    showUnresolved: boolean;
    showAttachments: boolean;
    showOrphans: boolean;
    showCooccurrences: boolean;
    colorGroups: ColorGroup[];
    showLabels: boolean;
    showArrows: boolean;
    nodeSizeScale: number;
    linkThicknessScale: number;
    textScale: number;
    labelThreshold: number;
    enableCollision: boolean;
    centerForce: number;
    repelForce: number;
    linkForce: number;
    linkDistance: number;
    applyStyling: () => void;
    rebuildGraph: () => void;
    saveGroups: () => void;
    addColorGroup: () => void;
    removeColorGroup: (idx: number) => void;
    resetForces: () => void;
  }

  let {
    searchQuery = $bindable(),
    showNotes = $bindable(),
    showTags = $bindable(),
    showUnresolved = $bindable(),
    showAttachments = $bindable(),
    showOrphans = $bindable(),
    showCooccurrences = $bindable(),
    colorGroups = $bindable(),
    showLabels = $bindable(),
    showArrows = $bindable(),
    nodeSizeScale = $bindable(),
    linkThicknessScale = $bindable(),
    textScale = $bindable(),
    labelThreshold = $bindable(),
    enableCollision = $bindable(),
    centerForce = $bindable(),
    repelForce = $bindable(),
    linkForce = $bindable(),
    linkDistance = $bindable(),
    applyStyling,
    rebuildGraph,
    saveGroups,
    addColorGroup,
    removeColorGroup,
    resetForces,
  }: Props = $props();

  let showSettingsPanel = $state(false);
  let activeSection: 'filters' | 'groups' | 'display' | 'forces' | null = $state('filters');

  function toggleSection(sec: 'filters' | 'groups' | 'display' | 'forces') {
    activeSection = activeSection === sec ? null : sec;
  }
</script>

<!-- GEAR / TOGGLE PANEL FLOATING BUTTON -->
<button
  class="settings-toggle-btn"
  class:panel-open={showSettingsPanel}
  title={$t('knowledgeGraphForce.settingsTitle')}
  onclick={() => (showSettingsPanel = !showSettingsPanel)}
>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="gear-icon"
    ><circle cx="12" cy="12" r="3"></circle><path
      d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a1.65 1.65 0 0 0 1-1.51H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
    ></path></svg
  >
</button>

<!-- OBSIDIAN STYLE COLLAPSIBLE FLOATING SIDEBAR PANEL -->
{#if showSettingsPanel}
  <div class="settings-sidebar" class:open={showSettingsPanel}>
    <div class="sidebar-header">
      <h4>{$t('knowledgeGraphForce.settingsTitle')}</h4>
      <button
        class="close-panel-btn"
        onclick={() => (showSettingsPanel = false)}
        aria-label={$t('knowledgeGraphForce.closePanel')}>×</button
      >
    </div>

    <div class="sidebar-scroll">
      <!-- 1. FILTROS -->
      <div class="accordion-item" class:active={activeSection === 'filters'}>
        <button
          type="button"
          class="accordion-header"
          onclick={() => toggleSection('filters')}
          aria-expanded={activeSection === 'filters'}
        >
          <span class="chevron" class:expanded={activeSection === 'filters'}>›</span>
          <h5>{$t('knowledgeGraphForce.filters')}</h5>
        </button>
        {#if activeSection === 'filters'}
          <div class="accordion-content">
            <div class="filter-search-wrap">
              <input
                class="panel-search"
                type="text"
                placeholder={$t('knowledgeGraphForce.searchPlaceholder')}
                bind:value={searchQuery}
                oninput={applyStyling}
              />
              {#if searchQuery}
                <button
                  class="panel-search-clear"
                  onclick={() => {
                    searchQuery = '';
                    applyStyling();
                  }}
                  aria-label={$t('knowledgeGraphForce.clearSearch')}>×</button
                >
              {/if}
            </div>

            <label class="toggle-control">
              <span>{$t('knowledgeGraphForce.files')}</span>
              <span class="switch">
                <input type="checkbox" bind:checked={showNotes} onchange={rebuildGraph} />
                <span class="slider"></span>
              </span>
            </label>

            <label class="toggle-control">
              <span>{$t('knowledgeGraphForce.tagsLabel')}</span>
              <span class="switch">
                <input type="checkbox" bind:checked={showTags} onchange={rebuildGraph} />
                <span class="slider"></span>
              </span>
            </label>

            <label class="toggle-control">
              <span>{$t('knowledgeGraphForce.nonExistentFiles')}</span>
              <span class="switch">
                <input type="checkbox" bind:checked={showUnresolved} onchange={rebuildGraph} />
                <span class="slider"></span>
              </span>
            </label>

            <label class="toggle-control">
              <span>{$t('knowledgeGraphForce.attachments')}</span>
              <span class="switch">
                <input type="checkbox" bind:checked={showAttachments} onchange={rebuildGraph} />
                <span class="slider"></span>
              </span>
            </label>

            <label class="toggle-control">
              <span>{$t('knowledgeGraphForce.orphans')}</span>
              <span class="switch">
                <input type="checkbox" bind:checked={showOrphans} onchange={rebuildGraph} />
                <span class="slider"></span>
              </span>
            </label>

            <label class="toggle-control">
              <span>{$t('knowledgeGraphForce.tagCooccurrences')}</span>
              <span class="switch">
                <input type="checkbox" bind:checked={showCooccurrences} onchange={rebuildGraph} />
                <span class="slider"></span>
              </span>
            </label>
          </div>
        {/if}
      </div>

      <!-- 2. GRUPOS DE COLOR -->
      <div class="accordion-item" class:active={activeSection === 'groups'}>
        <button
          type="button"
          class="accordion-header"
          onclick={() => toggleSection('groups')}
          aria-expanded={activeSection === 'groups'}
        >
          <span class="chevron" class:expanded={activeSection === 'groups'}>›</span>
          <h5>{$t('knowledgeGraphForce.colorGroups')}</h5>
        </button>
        {#if activeSection === 'groups'}
          <div class="accordion-content">
            <p class="section-desc">
              Pinta nodos según consultas (ej. <code>tag:idea</code>, <code>title:nota</code>)
            </p>

            <div class="groups-list">
              {#each colorGroups as group, idx}
                <div class="group-row">
                  <input
                    type="color"
                    class="color-picker-input"
                    bind:value={group.color}
                    onchange={saveGroups}
                  />
                  <input
                    type="text"
                    class="group-query-input"
                    placeholder="tag:idea o palabra clave..."
                    bind:value={group.query}
                    oninput={saveGroups}
                  />
                  <button
                    class="group-delete-btn"
                    title={$t('knowledgeGraphForce.removeRule')}
                    aria-label={$t('knowledgeGraphForce.removeRule')}
                    onclick={() => removeColorGroup(idx)}>×</button
                  >
                </div>
              {/each}
            </div>

            <button class="btn btn-ghost add-group-btn" onclick={addColorGroup}>
              + Añadir grupo
            </button>
          </div>
        {/if}
      </div>

      <!-- 3. VISUALIZACIÓN -->
      <div class="accordion-item" class:active={activeSection === 'display'}>
        <button
          type="button"
          class="accordion-header"
          onclick={() => toggleSection('display')}
          aria-expanded={activeSection === 'display'}
        >
          <span class="chevron" class:expanded={activeSection === 'display'}>›</span>
          <h5>{$t('knowledgeGraphForce.visualization')}</h5>
        </button>
        {#if activeSection === 'display'}
          <div class="accordion-content">
            <label class="toggle-control">
              <span>{$t('knowledgeGraphForce.showTextLabels')}</span>
              <span class="switch">
                <input type="checkbox" bind:checked={showLabels} onchange={applyStyling} />
                <span class="slider"></span>
              </span>
            </label>

            <label class="toggle-control">
              <span>{$t('knowledgeGraphForce.directionArrows')}</span>
              <span class="switch">
                <input type="checkbox" bind:checked={showArrows} />
                <span class="slider"></span>
              </span>
            </label>

            <label class="toggle-control">
              <span>{$t('knowledgeGraphForce.avoidOverlap')}</span>
              <span class="switch">
                <input type="checkbox" bind:checked={enableCollision} />
                <span class="slider"></span>
              </span>
            </label>

            <div class="slider-control">
              <div class="slider-lbl">
                <span>{$t('knowledgeGraphForce.nodeSize')}</span>
                <span>{nodeSizeScale.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="3.0"
                step="0.1"
                bind:value={nodeSizeScale}
                oninput={applyStyling}
              />
            </div>

            <div class="slider-control">
              <div class="slider-lbl">
                <span>{$t('knowledgeGraphForce.lineWidth')}</span>
                <span>{linkThicknessScale.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="3.0"
                step="0.1"
                bind:value={linkThicknessScale}
                oninput={applyStyling}
              />
            </div>

            <div class="slider-control">
              <div class="slider-lbl">
                <span>{$t('knowledgeGraphForce.textScale')}</span>
                <span>{textScale.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="2.0"
                step="0.1"
                bind:value={textScale}
                oninput={applyStyling}
              />
            </div>

            <div class="slider-control">
              <div class="slider-lbl">
                <span>{$t('knowledgeGraphForce.fadeThreshold')}</span>
                <span>{labelThreshold.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min="0.2"
                max="2.5"
                step="0.1"
                bind:value={labelThreshold}
                oninput={applyStyling}
              />
            </div>
          </div>
        {/if}
      </div>

      <!-- 4. FUERZAS FÍSICAS -->
      <div class="accordion-item" class:active={activeSection === 'forces'}>
        <button
          type="button"
          class="accordion-header"
          onclick={() => toggleSection('forces')}
          aria-expanded={activeSection === 'forces'}
        >
          <span class="chevron" class:expanded={activeSection === 'forces'}>›</span>
          <h5>{$t('knowledgeGraphForce.forces')}</h5>
        </button>
        {#if activeSection === 'forces'}
          <div class="accordion-content">
            <div class="slider-control">
              <div class="slider-lbl">
                <span>{$t('knowledgeGraphForce.repulsion')}</span>
                <span>{repelForce}</span>
              </div>
              <input type="range" min="30" max="600" step="10" bind:value={repelForce} />
            </div>

            <div class="slider-control">
              <div class="slider-lbl">
                <span>{$t('knowledgeGraphForce.linkDistance')}</span>
                <span>{linkDistance}px</span>
              </div>
              <input type="range" min="15" max="180" step="5" bind:value={linkDistance} />
            </div>

            <div class="slider-control">
              <div class="slider-lbl">
                <span>{$t('knowledgeGraphForce.linkAttraction')}</span>
                <span>{linkForce.toFixed(1)}</span>
              </div>
              <input type="range" min="0.1" max="2.0" step="0.1" bind:value={linkForce} />
            </div>

            <button class="btn btn-ghost reset-btn" onclick={resetForces}>
              Reestablecer fuerzas predeterminadas
            </button>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  /* SETTINGS PANEL FLOATING TOGGLE BUTTON */
  .settings-toggle-btn {
    position: absolute;
    top: 16px;
    left: 16px;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: color-mix(in srgb, var(--elevated) 85%, transparent);
    border: 1px solid color-mix(in srgb, var(--border) 60%, transparent);
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    z-index: var(--z-modal);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    backdrop-filter: blur(12px);
    transition:
      all 0.25s ease,
      opacity 0.2s ease;
    opacity: 0.4;
  }

  :global(.graph-wrapper):hover .settings-toggle-btn {
    opacity: 1;
  }

  .settings-toggle-btn:hover {
    color: var(--accent);
    background: var(--elevated);
    border-color: var(--accent);
  }

  .settings-toggle-btn.panel-open {
    left: 352px; /* move to the right of panel */
    color: var(--accent);
  }

  .gear-icon {
    width: 18px;
    height: 18px;
    transition: transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .settings-toggle-btn:hover .gear-icon,
  .settings-toggle-btn.panel-open .gear-icon {
    transform: rotate(45deg);
  }

  /* COLLAPSIBLE FLOATING SIDEBAR (GLASSMORPHISM) */
  .settings-sidebar {
    position: absolute;
    top: 16px;
    left: -336px; /* hide left initially */
    bottom: 16px;
    width: 320px;
    border-radius: 12px;
    background: rgba(20, 20, 20, 0.76);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(20px);
    z-index: var(--z-modal);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: left 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .settings-sidebar.open {
    left: 16px;
  }

  .sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    flex-shrink: 0;
  }

  .sidebar-header h4 {
    font-size: 13px;
    font-weight: 500;
    color: #e5e5e5;
    margin: 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .close-panel-btn {
    border: none;
    background: transparent;
    color: rgba(255, 255, 255, 0.4);
    font-size: 20px;
    cursor: pointer;
    line-height: 1;
    padding: 0;
    transition: color 0.15s ease;
  }

  .close-panel-btn:hover {
    color: #ffffff;
  }

  .sidebar-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  /* ACCORDION MODULES */
  .accordion-item {
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.04);
    overflow: hidden;
    transition: all 0.2s ease;
  }

  .accordion-item.active {
    background: rgba(255, 255, 255, 0.04);
    border-color: rgba(255, 255, 255, 0.08);
  }

  .accordion-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    cursor: pointer;
    user-select: none;
    width: 100%;
    background: transparent;
    border: none;
    text-align: left;
    color: inherit;
  }

  .accordion-header h5 {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-secondary);
    margin: 0;
  }

  .chevron {
    color: rgba(255, 255, 255, 0.35);
    font-size: 14px;
    font-weight: bold;
    display: inline-block;
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .chevron.expanded {
    transform: rotate(90deg);
    color: var(--accent);
  }

  .accordion-content {
    padding: 4px 12px 12px 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.03);
    animation: slideDown 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }

  @keyframes slideDown {
    from {
      opacity: 0;
      transform: translateY(-4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .section-desc {
    font-size: 10px;
    color: rgba(255, 255, 255, 0.4);
    margin: 0 0 4px 0;
    line-height: 1.3;
  }

  /* FILTERS & TOGGLES STYLE */
  .filter-search-wrap {
    position: relative;
    margin-bottom: 4px;
  }

  .panel-search {
    width: 100%;
    padding: 6px 26px 6px 8px;
    font-size: 11px;
    background: rgba(0, 0, 0, 0.35);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    outline: none;
    transition: border-color 0.15s ease;
  }

  .panel-search:focus {
    border-color: var(--accent);
  }

  .panel-search-clear {
    position: absolute;
    top: 50%;
    right: 8px;
    transform: translateY(-50%);
    border: none;
    background: transparent;
    color: rgba(255, 255, 255, 0.4);
    font-size: 14px;
    cursor: pointer;
    padding: 0;
  }

  .toggle-control {
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    font-size: 11px;
    color: #c7c7c7;
    user-select: none;
    padding: 3px 0;
  }

  .toggle-control span {
    transition: color 0.15s ease;
  }

  .toggle-control:hover span {
    color: #ffffff;
  }

  /* Premium iOS-style Switches */
  .switch {
    position: relative;
    display: inline-block;
    width: 28px;
    height: 16px;
    flex-shrink: 0;
  }

  .switch input {
    opacity: 0;
    width: 0;
    height: 0;
  }

  .slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(255, 255, 255, 0.12);
    transition: 0.2s;
    border-radius: 16px;
    border: 1.5px solid rgba(255, 255, 255, 0.08);
  }

  .slider:before {
    position: absolute;
    content: '';
    height: 10px;
    width: 10px;
    left: 2px;
    bottom: 1.5px;
    background-color: #ffffff;
    transition: 0.2s;
    border-radius: 50%;
  }

  input:checked + .slider {
    background-color: var(--accent, #1d9c73);
    border-color: var(--accent, #1d9c73);
  }

  input:checked + .slider:before {
    transform: translateX(12px);
  }

  /* COLOR GROUPS STYLE */
  .groups-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 140px;
    overflow-y: auto;
    padding-right: 2px;
  }

  .group-row {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(0, 0, 0, 0.2);
    padding: 4px 6px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.03);
  }

  .color-picker-input {
    -webkit-appearance: none;
    -moz-appearance: none;
    appearance: none;
    width: 18px;
    height: 18px;
    border: none;
    border-radius: 50%;
    cursor: pointer;
    background: transparent;
    padding: 0;
    flex-shrink: 0;
  }

  .color-picker-input::-webkit-color-swatch-wrapper {
    padding: 0;
  }

  .color-picker-input::-webkit-color-swatch {
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 50%;
  }

  .group-query-input {
    flex: 1;
    background: transparent;
    border: none;
    color: #ffffff;
    font-size: 11px;
    outline: none;
    padding: 2px 0;
  }

  .group-query-input::placeholder {
    color: rgba(255, 255, 255, 0.3);
  }

  .group-delete-btn {
    border: none;
    background: transparent;
    color: rgba(255, 255, 255, 0.4);
    font-size: 15px;
    cursor: pointer;
    padding: 0 4px;
    transition: color 0.15s ease;
  }

  .group-delete-btn:hover {
    color: #ff5555;
  }

  .add-group-btn {
    font-size: 10px;
    padding: 6px;
    width: 100%;
    text-align: center;
    border: 1px dashed rgba(255, 255, 255, 0.12);
    color: rgba(255, 255, 255, 0.6);
    border-radius: 6px;
    transition: all 0.15s ease;
  }

  .add-group-btn:hover {
    border-color: var(--accent);
    color: var(--accent);
    background: rgba(255, 255, 255, 0.02);
  }

  /* SLIDERS STYLE */
  .slider-control {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .slider-lbl {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: #b7b7b7;
  }

  .slider-lbl span:last-child {
    font-family: var(--font-mono, monospace);
    color: rgba(255, 255, 255, 0.4);
  }

  .slider-control input[type='range'] {
    width: 100%;
    height: 3px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 2px;
    outline: none;
    accent-color: var(--accent);
  }

  .reset-btn {
    font-size: 10px;
    padding: 8px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    color: rgba(255, 255, 255, 0.5);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .reset-btn:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.12);
  }

  /* Global buttons adjustments inside the widget */
  .btn-ghost {
    background: transparent;
    border: none;
    cursor: pointer;
  }
</style>
