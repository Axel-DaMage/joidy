<script lang="ts">
  export let width: string = '100%';
  export let height: string = '16px';
  export let rounded: 'sm' | 'md' | 'lg' | 'full' = 'md';
  export let lines = 1;
</script>

{#if lines === 1}
  <div
    class="skeleton rounded-{rounded}"
    style="width: {width}; height: {height};"
  ></div>
{:else}
  <div class="skeleton-lines">
    {#each Array(lines) as _, i}
      <div
        class="skeleton rounded-{rounded}"
        style="width: {i === lines - 1 ? '60%' : '100%'}; height: {height};"
      ></div>
    {/each}
  </div>
{/if}

<style>
  .skeleton {
    background: linear-gradient(
      90deg,
      var(--border-light, #2a2a2a) 0%,
      var(--border, #3a3a3a) 50%,
      var(--border-light, #2a2a2a) 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s ease-in-out infinite;
  }

  .skeleton-lines {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .rounded-sm { border-radius: 4px; }
  .rounded-md { border-radius: 8px; }
  .rounded-lg { border-radius: 12px; }
  .rounded-full { border-radius: 999px; }

  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
</style>