<script lang="ts">
  import LazyIconPicker from './LazyIconPicker.svelte';

  interface Props {
    open: boolean;
    customColor: string;
    updateFrontmatter: (key: string, value: string) => void;
    pickIcon: (icon: string) => void;
  }

  let {
    open = $bindable(),
    customColor = $bindable(),
    updateFrontmatter,
    pickIcon,
  }: Props = $props();
</script>

<!-- Icon customize modal -->
{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div
    class="folder-modal-backdrop"
    onclick={() => (open = false)}
    role="presentation"
    tabindex="-1"
  >
    <div
      class="folder-modal"
      onclick={(e) => e.stopPropagation()}
      role="presentation"
      tabindex="-1"
    >
      <h3 class="folder-modal-title">Personalizar icono</h3>

      <!-- Color bar -->
      <div class="folder-color-row">
        <span class="folder-label mono">Color</span>
        <input
          type="color"
          class="folder-color-input"
          bind:value={customColor}
          onchange={(e) => updateFrontmatter('iconColor', e.currentTarget.value)}
        />
        <input
          type="text"
          class="folder-hex-input mono"
          maxlength="7"
          bind:value={customColor}
          onchange={(e) => updateFrontmatter('iconColor', e.currentTarget.value)}
        />
      </div>

      <!-- Icon picker -->
      <div class="folder-icon-row">
        <LazyIconPicker
          color={customColor}
          onSelect={(ic) => {
            pickIcon(ic);
            open = false;
          }}
        />
      </div>

      <div class="folder-modal-btns">
        <button
          onclick={() => {
            updateFrontmatter('iconColor', '');
            updateFrontmatter('icon', '');
            updateFrontmatter('iconPack', '');
            customColor = '#ffffff';
            open = false;
          }}>Restablecer</button
        >
        <button onclick={() => (open = false)}>Cerrar</button>
      </div>
    </div>
  </div>
{/if}

<style>
  /* Icon customize modal */
  .folder-modal-backdrop {
    position: fixed;
    top: 50px;
    bottom: 50px;
    left: 0;
    right: 0;
    z-index: var(--z-overlay);
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(2px);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .folder-modal {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    width: 100%;
    height: 100%;
    max-width: 800px;
    min-height: 0;
  }
  .folder-modal-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }
  .folder-label {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .folder-color-row {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
  }
  .folder-color-input {
    flex: 1;
    height: 28px;
    border: 1px solid var(--border);
    border-radius: 4px;
    cursor: pointer;
    padding: 0;
    background: none;
  }
  .folder-color-input::-webkit-color-swatch-wrapper {
    padding: 0;
  }
  .folder-color-input::-webkit-color-swatch {
    border: none;
    border-radius: 3px;
  }
  .folder-hex-input {
    width: 75px;
    padding: 6px 8px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg);
    color: var(--text-primary);
    font-size: 11px;
    text-align: center;
    text-transform: uppercase;
  }
  .folder-icon-row {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
    min-height: 0;
  }
  .folder-modal-btns {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
  }
  .folder-modal-btns button {
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text-secondary);
    transition: all var(--t-fast);
  }
  .folder-modal-btns button:hover {
    background: var(--elevated);
    color: var(--text-primary);
  }
  .folder-modal-btns button:last-child {
    background: var(--accent);
    color: var(--accent-contrast-text, var(--bg));
    border-color: var(--accent);
  }
  .folder-modal-btns button:last-child:hover {
    opacity: 0.9;
  }
</style>
