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
  use:liquidGlass={{ enabled: streak.theme === 'glass' }}
>
  <button
    class="streak-item-main"
    on:click={() => dispatch('select', streak.id)}
    aria-label="Seleccionar racha: {streak.name}"
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
  </button>
  <div class="item-actions">
    <button
      class="item-action-btn"
      on:click|stopPropagation={() => dispatch('edit', streak)}
      title="Editar racha"
      aria-label="Editar racha: {streak.name}"
    >
      <Settings size={12} />
    </button>
    <button
      class="item-action-btn danger"
      on:click|stopPropagation={() => dispatch('delete', streak.id)}
      title="Eliminar racha"
      aria-label="Eliminar racha: {streak.name}"
    >
      <X size={12} />
    </button>
  </div>
</div>

<style>
  .streak-item {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 12px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; cursor: pointer;
    transition: all 0.15s; text-align: left; width: 100%;
    position: relative;
    overflow: hidden;
    isolation: isolate;
  }

  .streak-item > * {
    position: relative;
    z-index: 1;
  }

  .streak-item::before {
    content: '';
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s ease;
    z-index: 0;
  }

  .streak-item.theme-gradient {
    border-color: color-mix(in srgb, var(--theme-ac) 30%, var(--border));
  }

  .streak-item.theme-gradient::before {
    opacity: 1;
    background:
      linear-gradient(
        125deg,
        color-mix(in srgb, var(--theme-ac) 16%, transparent) 0%,
        transparent 45%,
        color-mix(in srgb, var(--theme-ac) 10%, transparent) 100%
      );
  }

  .streak-item.theme-glow {
    border-color: color-mix(in srgb, var(--theme-ac) 22%, var(--border));
    box-shadow:
      0 0 14px color-mix(in srgb, var(--theme-ac) 12%, transparent),
      inset 0 0 0 1px color-mix(in srgb, var(--theme-ac) 14%, transparent);
  }

  .streak-item.theme-glow::before {
    opacity: 1;
    background:
      radial-gradient(
        120% 90% at 50% 50%,
        color-mix(in srgb, var(--theme-ac) 12%, transparent) 0%,
        transparent 70%
      );
  }

  .streak-item.theme-minimal {
    background: color-mix(in srgb, var(--theme-ac) 8%, transparent);
    border: 1px solid transparent;
  }

  .streak-item.theme-lcd {
    background-color: var(--theme-ac);
    background-image:
      linear-gradient(rgba(0, 0, 0, 0.1) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0, 0, 0, 0.1) 1px, transparent 1px);
    background-size: 3px 3px;
    border: 1px solid color-mix(in srgb, var(--theme-ac) 70%, black);
    box-shadow: inset 0 0 10px rgba(0,0,0,0.15);
  }
  .streak-item.theme-lcd .item-num {
    font-family: var(--font-mono); color: color-mix(in srgb, var(--theme-ac) 20%, black) !important; text-shadow: none; font-weight: 800;
  }
  .streak-item.theme-lcd .item-name {
    color: color-mix(in srgb, var(--theme-ac) 20%, black) !important; opacity: 0.9; font-weight: 700;
  }
  .streak-item.theme-lcd .item-meta,
  .streak-item.theme-lcd .item-rem {
    color: color-mix(in srgb, var(--theme-ac) 20%, black) !important; opacity: 0.7; font-weight: 600;
  }
  .streak-item.theme-lcd .item-emoji,
  .streak-item.theme-lcd .item-icon {
    filter: grayscale(1) brightness(0) opacity(0.8);
  }
  .streak-item.theme-lcd .item-count :global(svg) {
    color: color-mix(in srgb, var(--theme-ac) 20%, black) !important;
  }

  .streak-item.theme-neon {
    background: color-mix(in srgb, var(--theme-ac) 8%, var(--surface));
    border: 1px solid var(--theme-ac);
    box-shadow: 0 0 10px color-mix(in srgb, var(--theme-ac) 25%, transparent);
  }
  .streak-item.theme-neon .item-name, .streak-item.theme-neon .item-num {
    text-shadow: 0 0 10px var(--theme-ac);
  }

  .streak-item.theme-glass {
    border: 1px solid transparent;
  }
  .streak-item.theme-solid {
    background: transparent;
    border: 1px solid var(--theme-ac);
  }

  .streak-item.theme-sketch {
    border: 1px dashed var(--theme-ac); border-radius: 2px;
  }

  .streak-item.theme-sketch .item-action-btn {
    border: 1px dashed var(--theme-ac);
    border-radius: 2px;
    background: transparent;
  }

  .streak-item.theme-sketch .item-action-btn:hover {
    background: color-mix(in srgb, var(--theme-ac) 10%, transparent);
  }

  .streak-item.theme-glow .item-action-btn,
  .streak-item.theme-gradient .item-action-btn,
  .streak-item.theme-neon .item-action-btn {
    border-color: transparent;
    background: transparent;
  }
  .streak-item.theme-glow .item-action-btn:hover,
  .streak-item.theme-gradient .item-action-btn:hover,
  .streak-item.theme-neon .item-action-btn:hover {
    border-color: transparent;
    background: color-mix(in srgb, var(--theme-ac) 10%, transparent);
  }

  .streak-item:hover { background: var(--elevated); }
  .streak-item.selected { background: var(--elevated); }
  .streak-item.completed {
    border-color: #10b981;
    background: rgba(16, 185, 129, 0.05);
  }
  .streak-item.completed .item-count { color: #10b981 !important; }

  .streak-item.archived { opacity: 0.5; }

  .streak-item.theme-gradient:hover,
  .streak-item.theme-glow:hover,
  .streak-item.theme-minimal:hover {
    background: var(--surface);
  }

  .streak-item.theme-gradient.selected,
  .streak-item.theme-glow.selected {
    background: var(--surface);
  }

  .streak-item.theme-lcd:hover,
  .streak-item.theme-lcd.selected {
    background-color: color-mix(in srgb, var(--theme-ac) 95%, black);
    background-image:
      linear-gradient(rgba(0, 0, 0, 0.1) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0, 0, 0, 0.1) 1px, transparent 1px);
    background-size: 3px 3px;
    box-shadow: inset 0 0 15px rgba(0,0,0,0.25);
  }

  .streak-item.theme-lcd .item-action-btn {
    border-color: color-mix(in srgb, var(--theme-ac) 70%, black);
    background: transparent;
    color: color-mix(in srgb, var(--theme-ac) 20%, black);
  }
  .streak-item.theme-lcd .item-action-btn:hover {
    border-color: color-mix(in srgb, var(--theme-ac) 20%, black);
    color: color-mix(in srgb, var(--theme-ac) 20%, black);
    background: color-mix(in srgb, black 15%, transparent);
  }
  .streak-item.theme-lcd .item-action-btn.danger:hover {
    border-color: color-mix(in srgb, var(--theme-ac) 20%, black);
    color: color-mix(in srgb, var(--theme-ac) 20%, black);
    background: color-mix(in srgb, black 30%, transparent);
  }

  .streak-item.theme-minimal.selected {
    background: var(--bg);
  }

  .streak-item.theme-minimal {
    filter: saturate(0.9) brightness(0.95);
  }

  .item-icon { font-size: 20px; flex-shrink: 0; width: 28px; text-align: center; }
  .item-emoji { font-size: 20px; }

  .item-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
  .item-name { font-size: 13px; font-weight: 500; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .item-meta { font-size: 9px; color: var(--text-disabled); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .item-count {
    display: flex; align-items: center; gap: 6px; flex-shrink: 0;
    padding-right: 24px;
  }

  .count-box {
    display: flex; flex-direction: column; align-items: flex-end; line-height: 1;
  }

  .item-rem {
    font-size: 8px; opacity: 0.6; margin-top: 1px;
  }
  .item-num { font-size: 18px; font-weight: 700; line-height: 1; }

  .item-actions {
    display: flex; flex-direction: column; gap: 3px;
    position: absolute; top: 6px; right: 6px;
    transition: opacity 0.15s;
  }

  @media (hover: hover) {
    .item-actions {
      opacity: 0; pointer-events: none;
    }
    .streak-item:hover .item-actions {
      opacity: 1;
      pointer-events: auto;
    }
  }

  @media (hover: none) {
    .item-actions {
      opacity: 0.5;
    }
    .item-action-btn {
      width: 24px; height: 24px;
    }
  }

  .item-action-btn {
    width: 20px; height: 20px;
    display: flex; align-items: center; justify-content: center;
    border: 1px solid var(--border); border-radius: 5px;
    background: var(--surface); color: var(--text-muted);
    padding: 0; cursor: pointer;
    transition: all 0.15s;
  }

  .item-action-btn:hover {
    border-color: var(--text-muted);
    color: var(--text-primary);
  }

  .item-action-btn.danger:hover {
    border-color: var(--error);
    color: var(--error);
  }

  .item-action-btn.confirm {
    border-color: var(--error);
    color: var(--error);
    background: color-mix(in srgb, var(--error) 10%, var(--surface));
  }

  @media (max-width: 768px) {
    .streak-item {
      flex-wrap: wrap;
      gap: 8px;
      padding: 10px;
    }

    .streak-item .item-count {
      padding-right: 0;
      margin-left: auto;
    }

    .streak-item .item-actions {
      position: static;
      opacity: 1 !important;
      pointer-events: auto !important;
      flex-direction: row;
      width: 100%;
      justify-content: flex-end;
      gap: 6px;
    }
  }

  .streak-item-main {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1;
    min-width: 0;
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    text-align: left;
    color: inherit;
    font: inherit;
}
</style>
