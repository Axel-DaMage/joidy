<script lang="ts">
  import type { Snippet } from 'svelte';

  // Shared absolute-positioned tooltip for the analytics charts (#1499).
  // `x`/`y` are px coordinates relative to the positioned chart wrapper;
  // `placeBelow` flips the tooltip under the cursor for top-edge points.
  let {
    x = 0,
    y = 0,
    visible = false,
    placeBelow = false,
    children,
  }: {
    x?: number;
    y?: number;
    visible?: boolean;
    placeBelow?: boolean;
    children?: Snippet;
  } = $props();
</script>

{#if visible}
  <div
    class="chart-tooltip"
    class:below={placeBelow}
    style="left: {x}px; top: {y}px;"
    role="tooltip"
  >
    {@render children?.()}
  </div>
{/if}

<style>
  .chart-tooltip {
    position: absolute;
    transform: translate(-50%, calc(-100% - 10px));
    pointer-events: none;
    z-index: 20;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-primary);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
    white-space: nowrap;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .chart-tooltip.below {
    transform: translate(-50%, 12px);
  }
  .chart-tooltip :global(.tt-title) {
    font-weight: 700;
    color: var(--text-secondary);
    text-transform: uppercase;
    font-size: 9px;
    letter-spacing: 0.05em;
  }
  .chart-tooltip :global(.tt-row) {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--text-muted);
  }
  .chart-tooltip :global(.tt-dot) {
    width: 7px;
    height: 7px;
    border-radius: 2px;
    flex-shrink: 0;
  }
  .chart-tooltip :global(.tt-val) {
    margin-left: auto;
    padding-left: 10px;
    font-weight: 700;
    color: var(--text-primary);
  }
</style>
