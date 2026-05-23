<script lang="ts">
  import { achievements } from '$lib/stores/achievements';
  import DynamicIcon from './DynamicIcon.svelte';
  import { fly } from 'svelte/transition';

  export let compact = false;

  $: unlockedCount = $achievements.filter(a => a.unlocked).length;
  $: totalCount = $achievements.length;
</script>

<div class="achievements-panel" class:compact>
  {#if !compact}
    <div class="achievements-header">
      <h4>Logros</h4>
      <span class="achievements-count">{unlockedCount}/{totalCount}</span>
    </div>
  {/if}

  <div class="achievements-grid">
    {#each $achievements as achievement (achievement.id)}
      <div
        class="achievement"
        class:unlocked={achievement.unlocked}
        title="{achievement.title}: {achievement.description}"
        transition:fly={{ y: 10, duration: 200 }}
      >
        <div class="achievement-icon">
          <DynamicIcon
            name={achievement.icon}
            size={compact ? 16 : 20}
            color={achievement.unlocked ? 'var(--accent)' : 'var(--text-muted)'}
          />
        </div>
        {#if !compact}
          <div class="achievement-info">
            <span class="achievement-title">{achievement.title}</span>
            <span class="achievement-desc">{achievement.description}</span>
          </div>
        {/if}
      </div>
    {/each}
  </div>
</div>

<style>
  .achievements-panel {
    padding: 12px 0;
  }

  .achievements-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }

  .achievements-header h4 {
    margin: 0;
    font-size: 14px;
    color: var(--text-primary);
  }

  .achievements-count {
    font-size: 12px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .achievements-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(40px, 1fr));
    gap: 8px;
  }

  .compact .achievements-grid {
    grid-template-columns: repeat(5, 1fr);
  }

  .achievement {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 8px;
    border-radius: 8px;
    background: var(--elevated);
    border: 1px solid var(--border-light);
    opacity: 0.4;
    transition: all var(--t-fast);
    cursor: default;
  }

  .achievement.unlocked {
    opacity: 1;
    border-color: var(--accent);
    box-shadow: 0 0 8px color-mix(in srgb, var(--accent) 20%, transparent);
  }

  .achievement:not(.compact) {
    flex-direction: row;
    justify-content: flex-start;
    gap: 10px;
  }

  .achievement-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .achievement-title {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-primary);
  }

  .achievement-desc {
    font-size: 10px;
    color: var(--text-muted);
  }

  .achievement-icon {
    display: flex;
    align-items: center;
    justify-content: center;
  }
</style>