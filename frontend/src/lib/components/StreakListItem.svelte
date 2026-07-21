<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { Check, Settings, X } from 'lucide-svelte';
  import StreakIcon from './StreakIcon.svelte';
  import { liquidGlass } from '$lib/actions/liquidGlass';

  export let streak: any;
  export let selected: boolean = false;
  export let streakLabel: (n: number) => string;
  export let freqLabel: (s: any) => string;
  export let isStreakCompleted: (s: any) => boolean;
  export let getDaysForCompletion: (s: any) => string;

  const dispatch = createEventDispatcher<{ select: number; edit: any; delete: number }>();
</script>

<div
  class="streak-item"
  class:theme-gradient={streak.theme === 'gradient'}
  class:theme-glow={streak.theme === 'glow'}
  class:theme-minimal={streak.theme === 'minimal'}
  class:theme-lcd={streak.theme === 'lcd'}
  class:theme-neon={streak.theme === 'neon'}
  class:theme-glass={streak.theme === 'glass'}
  class:theme-sketch={streak.theme === 'sketch'}
  class:theme-solid={!streak.theme || streak.theme === 'solid'}
  class:selected
  class:checked={streak.today_checked}
  class:archived={streak.is_archived}
  class:completed={isStreakCompleted(streak)}
  style="--theme-ac: {streak.color || 'var(--xp)'};"
  on:click={() => dispatch('select', streak.id)}
  on:keydown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      dispatch('select', streak.id);
    }
  }}
  role="button"
  tabindex="0"
  use:liquidGlass={{ enabled: streak.theme === 'glass' }}
>
  <div class="item-icon">
    {#if streak.icon && streak.icon.length > 0}
      <StreakIcon name={streak.icon} size={18} color={streak.color || undefined} />
    {:else}
      <span class="item-emoji">{streak.emoji || '🔥'}</span>
    {/if}
  </div>
  <div class="item-info">
    <span class="item-name">{streak.name}</span>
    <span class="item-meta mono">
      {#if isStreakCompleted(streak)}
        Finalizado {getDaysForCompletion(streak)} días
      {:else}
        {freqLabel(streak)}
      {/if}
    </span>
  </div>
  <div class="item-count" style="color: {streak.color || 'var(--xp)'};">
    <div class="count-box">
      <span class="item-num mono">{streakLabel(streak.current_streak)}</span>
      {#if streak.target_date && !isStreakCompleted(streak)}
        <span class="item-rem mono">{streak.days_remaining}d</span>
      {/if}
    </div>
    {#if streak.today_checked}
      <Check size={10} style="color: {streak.color || 'var(--xp)'};" />
    {/if}
  </div>
  <div class="item-actions">
    <button
      class="item-action-btn"
      on:click|stopPropagation={() => dispatch('edit', streak)}
      title="Editar racha"
    >
      <Settings size={12} />
    </button>
    <button
      class="item-action-btn danger"
      on:click|stopPropagation={() => dispatch('delete', streak.id)}
      title="Eliminar racha"
    >
      <X size={12} />
    </button>
  </div>
</div>
