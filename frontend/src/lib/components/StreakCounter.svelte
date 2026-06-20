<script lang="ts">
  import { currentStreak } from '$lib/stores/gamification';
</script>

<div class="streak" class:milestone={$currentStreak >= 7} title="Racha actual">
  <span class="streak-icon">{$currentStreak >= 30 ? '◆' : $currentStreak >= 7 ? '◈' : '◇'}</span>
  <span class="streak-count mono">{$currentStreak}</span>
  <span class="streak-label label">días</span>
</div>

<style>
  .streak {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    cursor: default;
    transition: border-color var(--t-normal);
  }

  .streak.milestone {
    border-color: var(--xp);
  }

  .streak-icon {
    font-size: 10px;
    color: var(--text-muted);
    line-height: 1;
  }

  .milestone .streak-icon {
    color: var(--xp);
  }

  .streak-count {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--xp);
    font-weight: 500;
    min-width: 16px;
  }

  .streak-label {
    font-size: 10px;
    color: var(--text-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
</style>
