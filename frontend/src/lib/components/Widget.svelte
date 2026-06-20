<script lang="ts">
  import type { WidgetId } from '$lib/stores/layout';

  export let id:    WidgetId;
  export let panel: 'left' | 'right';
  export let index: number;
  export let total: number;
</script>

<div class="widget">
  <slot />
</div>

<style>
  .widget {
    position: relative;
    width: 100%;
    background: transparent;
    overflow: hidden;
    box-shadow: none;
  }

  /* Force-neutral container even if older accent styles remain in cache/builds. */
  .widget::before,
  .widget::after {
    content: none !important;
    display: none !important;
  }
</style>
