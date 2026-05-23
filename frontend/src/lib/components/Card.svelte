<script lang="ts">
  export let padding: 'none' | 'sm' | 'md' | 'lg' = 'md';
  export let hoverable = false;
  export let clickable = false;
</script>

<div
  class="card padding-{padding}"
  class:hoverable
  class:clickable
  on:click
  role={clickable ? 'button' : undefined}
  tabindex={clickable ? 0 : undefined}
  on:keydown={(e) => clickable && e.key === 'Enter' && e.currentTarget.click()}
>
  <slot />
</div>

<style>
  .card {
    background: var(--elevated, #1a1a1a);
    border: 1px solid var(--border);
    border-radius: var(--r, 8px);
    transition: all var(--t-fast);
  }

  .padding-none { padding: 0; }
  .padding-sm { padding: 8px; }
  .padding-md { padding: 16px; }
  .padding-lg { padding: 24px; }

  .hoverable:hover {
    border-color: var(--accent, #6366f1);
    box-shadow: 0 0 0 1px var(--accent, #6366f1);
  }

  .clickable {
    cursor: pointer;
    user-select: none;
  }

  .clickable:hover {
    background: var(--hover);
  }

  .clickable:active {
    transform: scale(0.98);
  }
</style>