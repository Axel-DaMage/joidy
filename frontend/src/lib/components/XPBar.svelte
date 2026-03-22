<script lang="ts">
  import { totalXP, nextStageXP, plantProgress, xpEvents } from '$lib/stores/gamification';
</script>

<div class="xp-bar-wrapper">
  <div class="xp-meta">
    <span class="label">XP</span>
    <span class="xp-value mono">{$totalXP.toLocaleString()}</span>
    {#if $nextStageXP}
      <span class="xp-next muted">/ {$nextStageXP.toLocaleString()}</span>
    {/if}
  </div>
  <div class="progress-track">
    <div class="progress-fill" style="width: {$plantProgress}%"></div>
  </div>
</div>

<!-- Floating XP events -->
{#each $xpEvents as evt (evt.id)}
  <div
    class="xp-float"
    style="
      left: {evt.x ?? 50}%;
      top: {evt.y ?? 60}%;
      transform: translateX(-50%);
    "
  >
    +{evt.amount} XP
  </div>
{/each}

<style>
  .xp-bar-wrapper {
    display: flex;
    flex-direction: column;
    gap: 6px;
    width: 100%;
  }

  .xp-meta {
    display: flex;
    align-items: baseline;
    gap: 6px;
  }

  .xp-value {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--xp);
    font-weight: 500;
  }

  .xp-next {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-muted);
  }
</style>
