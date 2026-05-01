<script lang="ts">
  import '../app.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import SettingsPanel from '$lib/components/SettingsPanel.svelte';
  import { api } from '$lib/api';
  import { totalXP, loadStats, pingActivity, globalLevel, nextStageXP } from '$lib/stores/gamification';
  import { running, secondsLeft, phase } from '$lib/stores/pomodoro';
  import { initPomodoroSettings } from '$lib/stores/pomodoro';
  import { accentColors, activeIconPack, use24HourClock } from '$lib/stores/settings';

  const navItems = [
    { href: '/',        label: 'Dashboard', icon: 'Home' },
    { href: '/notes',   label: 'Notas',     icon: 'BookOpen' },
    { href: '/graph',   label: 'Grafo',     icon: 'Network' },
    { href: '/skills',  label: 'Skills',    icon: 'Zap' },
    { href: '/goals',   label: 'Objetivos', icon: 'Target' },
    { href: '/streaks', label: 'Rachas',    icon: 'Flame'  },
  ];

  let settingsOpen = false;
  let now = new Date();
  let pendingTasks = 0;
  let pendingStreaks = 0;

  $: currentTime = now.toLocaleTimeString('es-CL', {
    hour: $use24HourClock ? '2-digit' : 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: !$use24HourClock,
  });

  $: currentDate = now.toLocaleDateString('es-CL', {
    weekday: 'short',
    day: '2-digit',
    month: 'short'
  });

  onMount(() => {
    accentColors.init();
    activeIconPack.init();
    initPomodoroSettings();

    const loadFooterStats = async () => {
      try {
        const goals = await api.goals.list();
        pendingTasks = goals.filter((goal) => !goal.is_completed).length;
      } catch (e) {
        console.error('[layout] goals list failed:', e);
      }

      try {
        const streaks = await api.personalStreaks.list({ include_archived: false });
        pendingStreaks = streaks.filter((streak) => !streak.today_checked && !streak.is_archived).length;
      } catch (e) {
        console.error('[layout] personal streaks list failed:', e);
      }
    };

    const init = async () => {
      await loadFooterStats();
      try { await loadStats(); } catch (e) { console.error('[layout] loadStats failed:', e); }
      try { await pingActivity(); } catch (e) { console.error('[layout] pingActivity failed:', e); }
    };

    init().catch((e) => console.error('[layout] init failed:', e));

    const handleStreaksUpdated = () => {
      loadFooterStats().catch((e) => console.error('[layout] footer stats refresh failed:', e));
    };

    const handleWindowFocus = () => {
      loadFooterStats().catch((e) => console.error('[layout] footer stats refresh failed:', e));
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        loadFooterStats().catch((e) => console.error('[layout] footer stats refresh failed:', e));
      }
    };

    window.addEventListener('joidy:streaks-updated', handleStreaksUpdated);
    window.addEventListener('focus', handleWindowFocus);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    const clockInterval = setInterval(() => {
      now = new Date();
    }, 1000);

    const statsInterval = setInterval(() => {
      loadFooterStats().catch((e) => console.error('[layout] footer stats refresh failed:', e));
    }, 15000);

    return () => {
      clearInterval(clockInterval);
      clearInterval(statsInterval);
      window.removeEventListener('joidy:streaks-updated', handleStreaksUpdated);
      window.removeEventListener('focus', handleWindowFocus);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
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

    <div class="status-live" title="Estado actual">
      <span class="status-pill status-time mono">{currentTime}</span>
      <span class="status-pill status-date">{currentDate}</span>
      <span class="status-pill status-tasks">{pendingTasks} tareas</span>
      {#if pendingStreaks > 0}
        <span class="status-pill status-streak-alert" title="Rachas pendientes">
          <DynamicIcon name="Flame" size={12} color="var(--xp)" />
          <span>{pendingStreaks}</span>
        </span>
      {/if}
    </div>

    <div style="flex:1;"></div>

    <!-- Mini global Pomodoro -->
    <div class="mini-pomo" class:is-running={$running} class:is-break={$phase !== 'work'} title="Temporizador global">
      <span class="mono p-timer">{String(Math.floor($secondsLeft / 60)).padStart(2, '0')}:{String($secondsLeft % 60).padStart(2, '0')}</span>
      <span class="p-dot" class:beat={$running}></span>
    </div>
  </footer>
</div>

<SettingsPanel bind:open={settingsOpen} on:close={() => settingsOpen = false} />

<style>
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
    margin-left: 0;
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

  .status-live {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-right: 12px;
  }

  .status-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    line-height: 1;
    color: var(--xp);
    border: 1px solid color-mix(in srgb, var(--xp) 35%, var(--border));
    background: color-mix(in srgb, var(--xp) 10%, transparent);
    padding: 3px 7px;
    border-radius: 999px;
    white-space: nowrap;
  }

  .status-time {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.04em;
    line-height: 1;
    min-width: 92px;
    height: 20px;
    padding: 0 8px;
  }

  .status-date {
    text-transform: capitalize;
  }

  .status-streak-alert {
    border-color: color-mix(in srgb, var(--xp) 65%, var(--border));
    background: color-mix(in srgb, var(--xp) 18%, transparent);
    font-weight: 600;
  }

  @media (max-width: 900px) {
    .status-live {
      display: none;
    }
  }

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
