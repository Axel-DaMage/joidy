<script lang="ts">
  import type { WidgetId } from '$lib/stores/layout';
  import { WIDGET_REGISTRY } from '$lib/stores/layout';

  export let id: WidgetId;

  $: label = WIDGET_REGISTRY[id]?.label ?? id;
</script>

<div
  class="widget"
  role="listitem"
  aria-label={label}
>
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
  }

  .widget-content {
    width: 100%;
  }

  /* Force-neutral container even if older accent styles remain in cache/builds. */
  .widget::before,
  .widget::after {
    content: none;
    display: none;
  }
</style>
