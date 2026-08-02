<script lang="ts">
  /**
   * Shared progress bar component (#255).
   * Replaces duplicated progress-track/progress-fill markup across XPBar,
   * GoalCard, goals/+page, OnboardingTour, etc.
   */
  export let value = 0;
  export let max = 100;
  export let color = '';
  export let height = 6;
  export let variant: 'default' | 'success' = 'default';

  $: pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
</script>

<div class="progress-track" style="height: {height}px; border-radius: {Math.max(1, height / 2)}px;">
  <div
    class="progress-fill"
    class:success={variant === 'success'}
    style="width: {pct}%; {color ? `background: ${color};` : ''}"
  ></div>
</div>

<style>
  .progress-track {
    background: var(--border);
    overflow: hidden;
    position: relative;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--xp) 0%, var(--xp-2) 52%, var(--xp-3) 100%);
    transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .progress-fill.success {
    background: var(--success);
  }
</style>
