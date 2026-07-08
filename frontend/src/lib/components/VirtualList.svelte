<script lang="ts">
  import { onMount, tick } from 'svelte';

  export let items: any[] = [];
  export let itemHeight = 32; // This now acts as a default/fallback height
  export let buffer = 5;
  export let getKey: (item: any, index: number) => any = (item, i) => item.id ?? i;

  let scrollTop = 0;
  let containerEl: HTMLElement;
  let containerHeight = 400;

  // Track dynamic heights
  let heights: number[] = [];

  $: {
    if (heights.length !== items.length) {
      heights.length = items.length;
    }
  }

  // Calculate cumulative positions based on measured heights or fallback
  let positions: number[] = [];
  $: {
    let currentY = 0;
    positions = items.map((_, i) => {
      const p = currentY;
      currentY += (heights[i] || itemHeight);
      return p;
    });
  }

  // Calculate total height
  $: totalHeight = positions.length > 0 
    ? positions[positions.length - 1] + (heights[heights.length - 1] || itemHeight)
    : 0;

  // Binary search for start index (since positions is sorted)
  function findIndex(scrollTop: number) {
    let low = 0;
    let high = positions.length - 1;
    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const pos = positions[mid];
      const h = heights[mid] || itemHeight;
      if (pos <= scrollTop && pos + h > scrollTop) {
        return mid;
      }
      if (pos < scrollTop) {
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }
    return 0;
  }

  $: startIndex = Math.max(0, findIndex(scrollTop) - buffer);
  $: endIndex = Math.min(items.length, findIndex(scrollTop + containerHeight) + buffer + 1);

  $: visibleItems = items.slice(startIndex, endIndex);
  $: offsetY = positions[startIndex] || 0;

  function onScroll(e: Event) {
    const target = e.target as HTMLElement;
    scrollTop = target.scrollTop;
  }

  let ro: ResizeObserver;

  onMount(async () => {
    await tick();
    if (containerEl) {
      containerHeight = containerEl.clientHeight;
      ro = new ResizeObserver((entries) => {
        let changed = false;
        for (const entry of entries) {
          if (entry.target === containerEl) {
            containerHeight = containerEl.clientHeight;
          } else {
            const indexStr = (entry.target as HTMLElement).dataset.index;
            if (indexStr !== undefined) {
              const idx = parseInt(indexStr, 10);
              const height = entry.borderBoxSize?.[0]?.blockSize ?? entry.target.getBoundingClientRect().height;
              if (heights[idx] !== height) {
                heights[idx] = height;
                changed = true;
              }
            }
          }
        }
        if (changed) {
          heights = [...heights]; // trigger reactivity
        }
      });
      ro.observe(containerEl);
    }
    return () => {
      if (ro) ro.disconnect();
    };
  });

  // Action to observe individual item nodes
  function observeItem(node: HTMLElement, index: number) {
    node.dataset.index = index.toString();
    if (ro) ro.observe(node);
    
    // Initial sync
    const h = node.getBoundingClientRect().height;
    if (heights[index] !== h) {
      heights[index] = h;
      heights = [...heights];
    }

    return {
      update(newIndex: number) {
        node.dataset.index = newIndex.toString();
      },
      destroy() {
        if (ro) ro.unobserve(node);
      }
    };
  }
</script>

<div class="virtual-container" bind:this={containerEl} on:scroll={onScroll}>
  <div class="virtual-spacer" style="height: {totalHeight}px;">
    <div class="virtual-content" style="transform: translateY({offsetY}px);">
      {#each visibleItems as item, i (getKey(item, startIndex + i))}
        <div use:observeItem={startIndex + i}>
          <slot {item} index={startIndex + i} />
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .virtual-container {
    overflow-y: auto;
    overflow-x: hidden;
    height: 100%;
    will-change: scroll-position;
  }
  .virtual-spacer {
    position: relative;
    width: 100%;
  }
  .virtual-content {
    position: absolute;
    left: 0;
    top: 0;
    right: 0;
  }
</style>
