<script lang="ts">
  export let size: 'sm' | 'md' | 'lg' = 'md';
  export let color: string = 'var(--accent)';
</script>

<div class="spinner" class:sm={size === 'sm'} class:md={size === 'md'} class:lg={size === 'lg'} style="--spinner-color: {color}">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="10" stroke-opacity="0.25" />
    <path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round" />
  </svg>
</div>

<style>
  .spinner {
    display: inline-flex;
    animation: spin 1s linear infinite;
  }

  .spinner.sm { width: 14px; height: 14px; }
  .spinner.md { width: 20px; height: 20px; }
  .spinner.lg { width: 32px; height: 32px; }

  .spinner svg {
    width: 100%;
    height: 100%;
    color: var(--spinner-color);
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>