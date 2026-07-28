<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { WidgetId, DashboardLayout } from '$lib/stores/layout';
  import DynamicIcon from './DynamicIcon.svelte';
  import { WIDGET_REGISTRY } from '$lib/stores/layout';

  export let id:    WidgetId;
  export let panel: 'left' | 'right';
  export let index: number;
  export let total: number;
  export let layout: DashboardLayout;

  let dragOver = false;

  const dispatch = createEventDispatcher<{
    drop: { id: WidgetId; fromPanel: 'left' | 'right'; fromIdx: number; toPanel: 'left' | 'right'; toIdx: number };
  }>();

  function handleDragStart(e: DragEvent) {
    if (!e.dataTransfer) return;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', JSON.stringify({ id, panel, index }));
    e.dataTransfer.setData('application/x-widget', '');
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    if (!e.dataTransfer) return;
    e.dataTransfer.dropEffect = 'move';
    dragOver = true;
  }

  function handleDragLeave() {
    dragOver = false;
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    dragOver = false;
    if (!e.dataTransfer) return;
    try {
      const src = JSON.parse(e.dataTransfer.getData('text/plain'));
      if (src.id === id && src.panel === panel) return;
      dispatch('drop', {
        id: src.id as WidgetId,
        fromPanel: src.panel,
        fromIdx: src.index,
        toPanel: panel,
        toIdx: index,
      });
    } catch {}
  }

  $: label = WIDGET_REGISTRY[id]?.label ?? id;
</script>

<div
  class="widget"
  class:drag-over={dragOver}
  draggable="true"
  on:dragstart={handleDragStart}
  on:dragover={handleDragOver}
  on:dragleave={handleDragLeave}
  on:drop={handleDrop}
  on:dragend={() => { dragOver = false; }}
  role="listitem"
  aria-label={label}
>
  <div class="widget-handle">
    <DynamicIcon name="GripVertical" size={10} />
  </div>
  <div class="widget-content">
    <slot />
  </div>
</div>

<style>
  .widget {
    position: relative;
    width: 100%;
    background: transparent;
    overflow: hidden;
    box-shadow: none;
    transition: opacity var(--t-fast), border-color var(--t-fast);
  }

  .widget[draggable="true"] {
    cursor: grab;
  }

  .widget[draggable="true"]:active {
    cursor: grabbing;
    opacity: 0.6;
  }

  .widget.drag-over {
    border: 1px dashed var(--accent);
    border-radius: var(--r);
    opacity: 0.8;
  }

  .widget-handle {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2px 0;
    color: var(--text-muted);
    opacity: 0;
    transition: opacity var(--t-fast);
    cursor: grab;
    height: 12px;
  }

  .widget:hover .widget-handle {
    opacity: 0.5;
  }

  .widget-handle:hover {
    opacity: 1 !important;
  }

  .widget-content {
    width: 100%;
  }

  /* Force-neutral container even if older accent styles remain in cache/builds. */
  .widget::before,
  .widget::after {
    content: none !important;
    display: none !important;
  }
</style>
