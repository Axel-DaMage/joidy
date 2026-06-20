<script lang="ts">
  export let value = 0;
  export let max = 100;
  export let showLabel = false;
  export let variant: 'default' | 'success' | 'accent' = 'default';
  export let size: 'sm' | 'md' | 'lg' = 'md';

  $: percentage = Math.min(100, Math.max(0, (value / max) * 100));
</script>

<div class="progress-container progress-{size}">
  <div class="progress-bar">
    <div
      class="progress-fill progress-{variant}"
      style="width: {percentage}%"
    ></div>
  </div>
  {#if showLabel}
    <span class="progress-label">{Math.round(percentage)}%</span>
  {/if}
</div>

<style>
  .progress-container {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
  }

  .progress-bar {
    flex: 1;
    background: var(--border);
    border-radius: 999px;
    overflow: hidden;
  }

  .progress-sm .progress-bar { height: 4px; }
  .progress-md .progress-bar { height: 8px; }
  .progress-lg .progress-bar { height: 12px; }

  .progress-fill {
    height: 100%;
    border-radius: 999px;
    transition: width 0.3s ease;
  }

  .progress-default { background: var(--text-muted); }
  .progress-success { background: var(--success, #22c55e); }
  .progress-accent { background: var(--accent, #6366f1); }

  .progress-label {
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    min-width: 36px;
    text-align: right;
  }
</style>