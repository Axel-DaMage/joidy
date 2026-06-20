<script lang="ts">
  export let variant: 'default' | 'success' | 'warning' | 'error' | 'accent' = 'default';
  export let size: 'sm' | 'md' = 'md';
</script>

<span class="badge badge-{variant} badge-{size}">
  <slot />
</span>

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 500;
    white-space: nowrap;
  }

  .badge-sm { font-size: 10px; padding: 1px 6px; }
  .badge-md { font-size: 11px; padding: 2px 8px; }

  .badge-default {
    background: var(--elevated);
    color: var(--text-secondary);
    border: 1px solid var(--border);
  }

  .badge-success {
    background: color-mix(in srgb, var(--success, #22c55e) 15%, transparent);
    color: var(--success, #22c55e);
    border: 1px solid color-mix(in srgb, var(--success, #22c55e) 30%, transparent);
  }

  .badge-warning {
    background: color-mix(in srgb, var(--xp, #f59e0b) 15%, transparent);
    color: var(--xp, #f59e0b);
    border: 1px solid color-mix(in srgb, var(--xp, #f59e0b) 30%, transparent);
  }

  .badge-error {
    background: color-mix(in srgb, var(--error, #ef4444) 15%, transparent);
    color: var(--error, #ef4444);
    border: 1px solid color-mix(in srgb, var(--error, #ef4444) 30%, transparent);
  }

  .badge-accent {
    background: color-mix(in srgb, var(--accent, #6366f1) 15%, transparent);
    color: var(--accent, #6366f1);
    border: 1px solid color-mix(in srgb, var(--accent, #6366f1) 30%, transparent);
  }
</style>