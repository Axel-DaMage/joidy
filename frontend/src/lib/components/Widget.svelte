<script lang="ts">
  import { ChevronUp, ChevronDown, ArrowLeftRight } from 'lucide-svelte';
  import { dashboardLayout, editMode, WIDGET_REGISTRY, type WidgetId } from '$lib/stores/layout';

  export let id:    WidgetId;
  export let panel: 'left' | 'right';
  export let index: number;
  export let total: number;

  $: meta = WIDGET_REGISTRY[id];
  $: col  = $dashboardLayout[panel];

  function up()     { if (index > 0)           dashboardLayout.move(panel, index, index - 1); }
  function down()   { if (index < total - 1)    dashboardLayout.move(panel, index, index + 1); }
  function toggle() { dashboardLayout.switchPanel(id, panel); }
</script>

<div class="widget" class:editing={$editMode}>
  {#if $editMode}
    <div class="edit-handle">
      <span class="handle-label mono">{meta.label}</span>
      <div class="handle-actions">
        <button on:click={up}     disabled={index === 0}         title="Subir"><ChevronUp   size={11}/></button>
        <button on:click={down}   disabled={index === total - 1} title="Bajar"><ChevronDown size={11}/></button>
        <button on:click={toggle} title="Mover al otro panel"><ArrowLeftRight size={11}/></button>
      </div>
    </div>
  {/if}
  <slot />
</div>

<style>
  .widget {
    position: relative;
    width: 100%;
  }

  .widget.editing {
    outline: 1px dashed color-mix(in srgb, var(--xp) 50%, transparent);
    border-radius: 4px;
  }

  .edit-handle {
    position: absolute;
    top: 4px;
    right: 4px;
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 4px;
    background: var(--surface);
    border: 1px solid var(--xp);
    border-radius: 4px;
    padding: 2px 6px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.4);
  }

  .handle-label {
    font-size: 9px;
    color: var(--xp);
    letter-spacing: 0.08em;
    white-space: nowrap;
  }

  .handle-actions {
    display: flex;
    gap: 2px;
  }

  .handle-actions button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 3px;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 80ms;
  }
  .handle-actions button:hover:not(:disabled) {
    background: var(--elevated);
    color: var(--text-primary);
  }
  .handle-actions button:disabled { opacity: 0.25; cursor: default; }
</style>
