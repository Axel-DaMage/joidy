<script lang="ts">
  import { totalXP, nextStageXP, plantProgress, xpEvents } from '$lib/stores/gamification';
</script>

<div class="xp-bar-wrapper">
  <div class="xp-meta">
    <div class="xp-badge">XP</div>
    <div class="xp-stats">
      <span class="xp-current">{$totalXP.toLocaleString()}</span>
      {#if $nextStageXP}
        <span class="xp-divider">/</span>
        <span class="xp-next">{$nextStageXP.toLocaleString()}</span>
      {:else}
        <span class="xp-divider">/</span>
        <span class="xp-next">MAX</span>
      {/if}
    </div>
  </div>
  <div class="progress-track">
    <div class="progress-fill" style="width: {$plantProgress}%">
      <div class="progress-glow"></div>
    </div>
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
    gap: 10px;
    width: 100%;
    padding: 12px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: var(--r);
    backdrop-filter: blur(5px);
  }

  .xp-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .xp-badge {
    background: var(--accent-gradient, var(--xp));
    color: var(--accent-contrast-text, var(--bg));
    font-size: 10px;
    font-weight: 800;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: var(--font-mono);
  }

  .xp-stats {
    display: flex;
    align-items: baseline;
    gap: 4px;
  }

  .xp-current {
    font-family: var(--font-mono);
    font-size: 16px;
    color: var(--text-primary);
    font-weight: 600;
    text-shadow: 0 0 10px color-mix(in srgb, var(--xp) 35%, transparent);
  }

  .xp-divider { color: var(--text-muted); font-size: 12px; }

  .xp-next {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-muted);
  }

  .progress-track {
    height: 6px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 3px;
    overflow: hidden;
    position: relative;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--xp-dark, var(--xp-2)) 0%, var(--xp) 55%, var(--xp-3) 100%);
    border-radius: 3px;
    transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
    position: relative;
  }

  .progress-glow {
    position: absolute;
    top: 0;
    right: 0;
    width: 20px;
    height: 100%;
    background: white;
    box-shadow: 0 0 15px 5px white;
    opacity: 0.3;
  }

  .xp-float {
    position: fixed;
    pointer-events: none;
    color: var(--xp);
    font-weight: 800;
    font-family: var(--font-mono);
    font-size: 18px;
    z-index: 2000;
    animation: xp-float-anim 1s ease-out forwards;
    text-shadow: 0 0 10px color-mix(in srgb, var(--xp) 45%, transparent);
  }

  @keyframes xp-float-anim {
    0% { transform: translate(-50%, 0) scale(0.5); opacity: 0; }
    20% { transform: translate(-50%, -20px) scale(1.2); opacity: 1; }
    100% { transform: translate(-50%, -60px) scale(1); opacity: 0; }
  }
</style>
