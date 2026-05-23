<script lang="ts">
  import { onMount, tick } from 'svelte';

  export let items: any[] = [];
  export let itemHeight = 32;
  export let buffer = 5;
  export let getKey: (item: any, index: number) => any = (item, i) => item.id ?? i;

  let scrollTop = 0;
  let containerEl: HTMLElement;
  let containerHeight = 400;

  $: totalHeight = items.length * itemHeight;
  $: startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - buffer);
  $: endIndex = Math.min(items.length, Math.ceil((scrollTop + containerHeight) / itemHeight) + buffer);
  $: visibleItems = items.slice(startIndex, endIndex);
  $: offsetY = startIndex * itemHeight;

  function onScroll(e: Event) {
    const target = e.target as HTMLElement;
    scrollTop = target.scrollTop;
  }

  onMount(async () => {
    await tick();
    if (containerEl) {
      containerHeight = containerEl.clientHeight;
      const ro = new ResizeObserver(() => {
        if (containerEl) {
          containerHeight = containerEl.clientHeight;
        }
      });
      ro.observe(containerEl);
    }
  });
</script>

<div class="virtual-container" bind:this={containerEl} on:scroll={onScroll}>
  <div class="virtual-spacer" style="height: {totalHeight}px;">
    <div class="virtual-content" style="transform: translateY({offsetY}px);">
      {#each visibleItems as item, i (getKey(item, startIndex + i))}
        <slot {item} index={startIndex + i} />
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