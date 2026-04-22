<script lang="ts">
  import '../app.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import SettingsPanel from '$lib/components/SettingsPanel.svelte';
  import { totalXP, loadStats, pingActivity, globalLevel, nextStageXP } from '$lib/stores/gamification';
  import { running, secondsLeft, phase } from '$lib/stores/pomodoro';
  import { editMode } from '$lib/stores/layout';
  import { accentColors, activeIconPack } from '$lib/stores/settings';

  const navItems = [
    { href: '/',        label: 'Dashboard', icon: 'Home' },
    { href: '/notes',   label: 'Notas',     icon: 'BookOpen' },
    { href: '/graph',   label: 'Grafo',     icon: 'Network' },
    { href: '/skills',  label: 'Skills',    icon: 'Zap' },
    { href: '/goals',   label: 'Objetivos', icon: 'Target' },
    { href: '/streaks', label: 'Rachas',    icon: 'Flame'  },
  ];

  let settingsOpen = false;

  onMount(async () => {
    accentColors.init();
    activeIconPack.init();
    try { await loadStats(); } catch (e) { console.error('[layout] loadStats failed:', e); }
    try { await pingActivity(); } catch (e) { console.error('[layout] pingActivity failed:', e); }
  });
</script>

<div class="app-shell">
  <!-- Header -->
  <header class="app-header">
    <span class="logo mono">JOIDY</span>
    <div style="flex:1;"></div>
    <span class="mono" style="font-size:13px; color: var(--xp); display: flex; align-items: center; gap: 8px;">
      <span>
        {$totalXP.toLocaleString()} 
        <span style="font-size:10px; color: var(--text-muted);">/ {$nextStageXP ? $nextStageXP.toLocaleString() : 'MAX'} xp</span>
      </span>
      <span style="font-size:11px; color: var(--text-primary); background: var(--surface); border: 1px solid var(--border); padding: 2px 6px; border-radius: 4px;">NVL {$globalLevel}</span>
    </span>
    <button
      class="btn btn-ghost btn-icon"
      title="Ajustes"
      style="color: var(--text-muted);"
      on:click={() => settingsOpen = true}
    >
      <DynamicIcon name="Settings" size={14} />
    </button>
  </header>

  <!-- Sidebar -->
  <nav class="app-sidebar">
    {#each navItems as { href, label, icon }}
      {@const active = $page.url.pathname === href || ($page.url.pathname.startsWith(href) && href !== '/')}
      <a {href} class="nav-item" class:active title={label}>
        <DynamicIcon name={icon} size={16} />
        <span class="tooltip">{label}</span>
      </a>
    {/each}
  </nav>

  <!-- Main content -->
  <main class="app-main">
    <slot />
  </main>

  <!-- Status bar -->
  <footer class="app-statusbar">
    <span style="color: var(--text-muted);">joidy v0.1</span>
    
    <!-- Mini global Pomodoro -->
    <div class="mini-pomo" class:is-running={$running} class:is-break={$phase !== 'work'} title="Temporizador global">
      <span class="mono p-timer">{String(Math.floor($secondsLeft / 60)).padStart(2, '0')}:{String($secondsLeft % 60).padStart(2, '0')}</span>
      <span class="p-dot" class:beat={$running}></span>
    </div>

    <div style="flex:1;"></div>
    <button
      class="edit-toggle"
      class:active={$editMode}
      on:click={() => editMode.update(v => !v)}
      title={$editMode ? 'Salir del modo edición' : 'Editar layout'}
    >
      <DynamicIcon name="LayoutGrid" size={12} />
    </button>
  </footer>
</div>

<SettingsPanel bind:open={settingsOpen} on:close={() => settingsOpen = false} />

<style>
  .edit-toggle {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
    border-radius: var(--r);
    transition: color var(--t-fast);
  }
  .edit-toggle:hover { color: var(--text-secondary); }
  .edit-toggle.active { color: var(--xp); }

  .logo {
    user-select: none;
    font-size: 15px;
    letter-spacing: 0.12em;
    font-weight: 500;
    background: var(--accent-gradient, var(--xp));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .mini-pomo {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: 20px;
    padding: 2px 8px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--elevated);
    color: var(--text-disabled);
    transition: all var(--t-normal);
  }
  .mini-pomo.is-running { color: var(--xp); border-color: var(--xp); background: color-mix(in srgb, var(--xp) 5%, transparent); }
  .mini-pomo.is-break { color: var(--success); border-color: var(--success); }
  .p-timer { font-size: 11px; }

  .p-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    opacity: 0.5;
  }
  .p-dot.beat {
    animation: p-beat 1.5s infinite;
  }
  @keyframes p-beat {
    0%, 100% { opacity: 0.3; transform: scale(0.9); }
    50%      { opacity: 1; transform: scale(1.1); box-shadow: 0 0 5px currentColor; }
  }
</style>
