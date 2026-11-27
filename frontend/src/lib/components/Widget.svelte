<script lang="ts">
  import type { WidgetId } from '$lib/stores/layout';
  import { WIDGET_REGISTRY } from '$lib/stores/layout';

  export let id: WidgetId;
  /** Position inside the parent list — drives the `--m-i` stagger delay on
      the shared `m-rise` entrance (motion system, #1657). */
  export let index = 0;

  $: label = WIDGET_REGISTRY[id]?.label ?? id;
</script>

<div
  class="widget m-rise"
  role="listitem"
  aria-label={label}
  style="--m-i:{Math.min(index, 6)}"
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
    flex-shrink: 0;
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
