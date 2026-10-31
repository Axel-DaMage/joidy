<script lang="ts">
  interface Props {
    padding?: 'none' | 'sm' | 'md' | 'lg';
    hoverable?: boolean;
    clickable?: boolean;
    children?: import('svelte').Snippet;
  }

  let {
    padding = 'md',
    hoverable = false,
    clickable = false,
    children,
  }: Props = $props();
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
  class="card padding-{padding}"
  class:hoverable
  class:clickable
  role={clickable ? 'button' : undefined}
  tabindex={clickable ? 0 : undefined}
  aria-label={clickable ? 'Card' : undefined}
  onkeydown={(e) => clickable && (e.key === 'Enter' || e.key === ' ') && e.currentTarget.click()}
>
  {@render children?.()}
</div>

<style>
  .card {
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    transition: all var(--t-fast);
  }

  .padding-none { padding: 0; }
  .padding-sm { padding: 8px; }
  .padding-md { padding: 16px; }
  .padding-lg { padding: 24px; }

  .hoverable:hover {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
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
