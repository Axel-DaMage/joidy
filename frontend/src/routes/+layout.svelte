<script lang="ts">
  import '../app.css';
  import { browser } from '$app/environment';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import { isOnline, wasOffline } from '$lib/stores/connection';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import SettingsPanel from '$lib/components/SettingsPanel.svelte';
  import CommandPalette from '$lib/components/CommandPalette.svelte';
  import Toast from '$lib/components/Toast.svelte';
  import Login from '$lib/components/Login.svelte';
  import { api, type Goal, type PersonalStreak } from '$lib/api';
  import { session, isAuthenticated } from '$lib/stores/session';
  import { totalXP, loadStats, pingActivity, globalLevel, nextStageXP, showNotification } from '$lib/stores/gamification';
  import { running, secondsLeft, phase } from '$lib/stores/pomodoro';
  import { initPomodoroSettings } from '$lib/stores/pomodoro';
  import { accentColors, activeIconPack, use24HourClock, initTheme, devMode } from '$lib/stores/settings';
  import { getCachedData, setCachedData } from '$lib/utils/userSettings';
  import { initKeyboardNavigation } from '$lib/utils/keyboardNavigation';
  import { logger } from '$lib/utils/logger';
  import { onboarding } from '$lib/stores/onboarding';
  import TutorialOverlay from '$lib/components/TutorialOverlay.svelte';
  import { achievements } from '$lib/stores/achievements';
  import { initConnectionStore } from '$lib/stores/connection';
  import { loadNotes } from '$lib/stores/notes';
  import { deferredPrompt, showInstallBanner, isAppInstalled } from '$lib/stores/pwa';

  type NavItemStatus = 'ready' | 'dev' | 'placeholder';

  const navItems: { href: string; label: string; icon: string; status: NavItemStatus }[] = [
    { href: '/',        label: 'Inicio',      icon: 'Home',     status: 'ready' },
    { href: '/notes',   label: 'Notas',       icon: 'BookOpen', status: 'ready' },
    { href: '/graph',   label: 'Grafo',       icon: 'Network',  status: 'dev' },
    { href: '/skills',  label: 'Habilidades', icon: 'Zap',      status: 'dev' },
    { href: '/goals',   label: 'Objetivos',   icon: 'Target',   status: 'ready' },
    { href: '/streaks', label: 'Rachas',      icon: 'Flame',    status: 'ready' },
    { href: '/ai',      label: 'IA',          icon: 'Brain',    status: 'placeholder' },
    { href: '/gmail',   label: 'Gmail',       icon: 'Mail',     status: 'placeholder' },
    { href: '/contactos', label: 'Contactos', icon: 'Users',    status: 'placeholder' },
    { href: '/strava',  label: 'Strava',      icon: 'Activity', status: 'placeholder' },
    { href: '/spotify', label: 'Spotify',     icon: 'Music',    status: 'placeholder' },
  ];

  let settingsOpen = false;
  let now = new Date();
  let pendingTasks = 0;
  let pendingStreaks = 0;
  let streaksNotified = false;
  let lastFooterStatsFetch = 0;
  let lastStatsLoad = 0;

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

  let mounted = false;

  onMount(() => {
    mounted = true;
    accentColors.init();
    activeIconPack.init();
    initTheme();
    initPomodoroSettings();
    initKeyboardNavigation();
    onboarding.init();
    achievements.init();
    devMode.init();
    const cleanupConnection = initConnectionStore();

    // Connect to WebSocket for real-time notifications
    let ws: WebSocket | null = null;
    let wsReconnectTimeout: any = null;
    let wsRetryDelay = 1000;

    const connectWS = () => {
      if (typeof window === 'undefined') return;

      if (!navigator.onLine) {
        logger.info('[layout] Offline, skipping WebSocket reconnect');
        return;
      }

      if (document.visibilityState === 'hidden') {
        logger.info('[layout] Tab hidden, skipping WebSocket reconnect');
        return;
      }
      
      const host = window.location.hostname;
      const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProto}//${host}:8000/ws`;

      logger.info('[layout] Connecting to WebSocket:', wsUrl);
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        logger.info('[layout] WebSocket connected');
        wsRetryDelay = 1000;
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          logger.info('[layout] WebSocket message received:', msg);
          
          if (msg.type === 'note_created') {
            showNotification(`Nueva nota creada: "${msg.title}"`, 'success');
            loadNotes(undefined, true).catch(() => {});
          } else if (msg.type === 'note_updated') {
            showNotification(`Nota actualizada: "${msg.title}"`, 'info');
            loadNotes(undefined, true).catch(() => {});
          } else if (msg.type === 'xp_gained') {
            showNotification(`¡+${msg.xp} XP!`, 'level');
            loadStats().catch(() => {});
          } else if (msg.type === 'streak_updated') {
            showNotification(`¡Racha de ${msg.streak} días! 🔥`, 'info');
            loadStats().catch(() => {});
          }
        } catch (e) {
          logger.error('[layout] Error parsing WebSocket message:', e);
        }
      };

      ws.onclose = () => {
        if (wsReconnectTimeout) clearTimeout(wsReconnectTimeout);
        const delay = Math.min(wsRetryDelay, 60000);
        logger.warn(`[layout] WebSocket connection closed, reconnecting in ${delay}ms...`);
        wsReconnectTimeout = setTimeout(connectWS, delay);
        wsRetryDelay = Math.min(wsRetryDelay * 2, 60000);
      };

      ws.onerror = (err) => {
        logger.error('[layout] WebSocket error:', err);
        ws?.close();
      };
    };

    connectWS();

    // Register service worker for PWA
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/service-worker.js').catch((err) => {
        logger.warn('SW registration failed:', err);
      });
    }

    window.addEventListener('appinstalled', () => {
      showNotification("¡Joidy instalado! Ahora puedes acceder desde tu escritorio.", "success");
    });

    const loadFooterStats = async (force = false) => {
      if (document.visibilityState !== 'visible') return;

      const now = Date.now();
      if (!force && now - lastFooterStatsFetch < 30000) return;
      lastFooterStatsFetch = now;

      const cachedGoals = getCachedData<Goal[]>('goals');
      const cachedStreaks = getCachedData<PersonalStreak[]>('streaks');
      if (cachedGoals) {
        pendingTasks = cachedGoals.filter((goal: Goal) => !goal.is_completed).length;
      }
      if (cachedStreaks) {
        pendingStreaks = cachedStreaks.filter((streak: PersonalStreak) => !streak.today_checked && !streak.is_archived).length;
      }
      
      try {
        const goals = await api.goals.list();
        pendingTasks = goals.filter((goal) => !goal.is_completed).length;
        setCachedData('goals', goals);
      } catch (e) {
        logger.error('[layout] goals list failed:', e);
      }

      try {
        const streaks = await api.personalStreaks.list({ include_archived: false });
        const newPendingStreaks = streaks.filter((streak) => !streak.today_checked && !streak.is_archived).length;
        pendingStreaks = newPendingStreaks;
        setCachedData('streaks', streaks);
        
        if (newPendingStreaks > 0 && !streaksNotified) {
          streaksNotified = true;
          showNotification(`Tienes ${newPendingStreaks} rachas pendientes hoy!`, 'info');
        }
      } catch (e) {
        logger.error('[layout] personal streaks list failed:', e);
      }
    };

    const throttledPing = async () => {
      const lastPing = localStorage.getItem('joidy-last-ping');
      if (lastPing) {
        const elapsed = Date.now() - parseInt(lastPing, 10);
        if (elapsed < 6 * 60 * 60 * 1000) return;
      }
      try {
        await pingActivity();
        localStorage.setItem('joidy-last-ping', Date.now().toString());
      } catch (e) {
        logger.error('[layout] pingActivity failed:', e);
      }
    };

    const throttledLoadStats = async () => {
      const now = Date.now();
      if (now - lastStatsLoad < 5 * 60 * 1000) return;
      lastStatsLoad = now;
      try {
        await loadStats();
      } catch (e) {
        logger.error('[layout] loadStats failed:', e);
      }
    };

    const init = async () => {
      loadFooterStats().catch(() => {});
      throttledLoadStats();
      throttledPing();
    };
    requestAnimationFrame(() => init());

    // Global error handlers
    const handleOnerror = (
      _event: Event | string,
      _source?: string,
      _lineno?: number,
      _colno?: number,
      error?: Error
    ) => {
      const msg = error?.message || String(error) || 'Error global';
      console.error('[Global onerror]', error);
      showNotification(`Error inesperado: ${msg}`, 'error');
    };
    window.onerror = handleOnerror;

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const reason = event.reason;
      const msg = reason?.message || String(reason) || 'Promesa rechazada';
      console.error('[Unhandled rejection]', reason);
      showNotification(`Error inesperado: ${msg}`, 'error');
    };
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    const handleStreaksUpdated = () => {
      loadFooterStats().catch((e) => logger.error('[layout] footer stats refresh failed:', e));
    };

    const handleOpenSettings = () => {
      settingsOpen = true;
    };

    const handleWindowFocus = () => {
      if (document.visibilityState === 'visible') {
        loadFooterStats(true).catch((e) => logger.error('[layout] footer stats refresh failed:', e));
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        if (Date.now() - lastFooterStatsFetch > 60000) {
          loadFooterStats(true).catch((e) => logger.error('[layout] footer stats refresh failed:', e));
        }
        if (!ws || (ws.readyState !== WebSocket.OPEN && ws.readyState !== WebSocket.CONNECTING)) {
          if (wsReconnectTimeout) clearTimeout(wsReconnectTimeout);
          wsRetryDelay = 1000;
          connectWS();
        }
      }
    };

    const handleOnline = () => {
      logger.info('[layout] Back online, reconnecting WebSocket...');
      if (wsReconnectTimeout) clearTimeout(wsReconnectTimeout);
      wsRetryDelay = 1000;
      connectWS();
    };

    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      deferredPrompt.set(e);
      
      if (!$isAppInstalled) {
        const visits = parseInt(localStorage.getItem('joidy-visits') || '0');
        localStorage.setItem('joidy-visits', (visits + 1).toString());
        
        if (visits >= 1 && localStorage.getItem('joidy-pwa-dismissed') !== 'true') {
          showInstallBanner.set(true);
        }
      }
    });

    window.addEventListener('online', handleOnline);
    window.addEventListener('joidy:streaks-updated', handleStreaksUpdated);
    window.addEventListener('joidy:open-settings', handleOpenSettings);
    window.addEventListener('focus', handleWindowFocus);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    const clockInterval = setInterval(() => {
      now = new Date();
    }, 1000);

    const statsInterval = setInterval(() => {
      loadFooterStats().catch((e) => logger.error('[layout] footer stats refresh failed:', e));
    }, 60000);

    return () => {
      clearInterval(clockInterval);
      clearInterval(statsInterval);
      window.removeEventListener('joidy:streaks-updated', handleStreaksUpdated);
      window.removeEventListener('joidy:open-settings', handleOpenSettings);
      window.removeEventListener('focus', handleWindowFocus);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);

      // Clean up WebSocket connection
      if (ws) {
        ws.onclose = null; // Prevent reconnect loop
        ws.close();
      }
      if (wsReconnectTimeout) clearTimeout(wsReconnectTimeout);
    };
  });
  let showConnectedPill = false;
  let pillTimeout: any = null;

  $: if ($isOnline && $wasOffline) {
    showConnectedPill = true;
    wasOffline.set(false);
    if (pillTimeout) clearTimeout(pillTimeout);
    pillTimeout = setTimeout(() => {
      showConnectedPill = false;
    }, 4000);
  }
</script>

{#if !mounted}
  <!-- Render blank or loading during SSR to prevent hydration mismatch -->
  <div style="min-height: 100vh; background: var(--bg);"></div>
{:else if !$isAuthenticated}
  <Login />
  <Toast />
{:else}
<div class="app-shell">
  <!-- Header -->
  <header class="app-header">
    <span class="logo mono">JOIDY</span>
    
    {#if $showInstallBanner}
      <div class="pwa-banner" transition:fade={{ duration: 150 }}>
        <DynamicIcon name="DownloadCloud" size={13} />
        <span>Instala Joidy para acceso rápido</span>
        <div class="pwa-actions">
          <button class="pwa-btn pwa-install" on:click={async () => {
            if ($deferredPrompt) {
              $deferredPrompt.prompt();
              const { outcome } = await $deferredPrompt.userChoice;
              if (outcome === 'accepted') {
                showInstallBanner.set(false);
              }
              deferredPrompt.set(null);
            }
          }}>Instalar</button>
          <button class="pwa-btn pwa-dismiss" on:click={() => {
            showInstallBanner.set(false);
            localStorage.setItem('joidy-pwa-dismissed', 'true');
          }}>
            <DynamicIcon name="X" size={12} />
          </button>
        </div>
      </div>
    {/if}

    <div style="flex:1;"></div>

    <!-- Connectivity Indicator -->
    {#if !$isOnline}
      <div class="connectivity-pill offline" transition:fade={{ duration: 150 }}>
        <span class="pulse-dot red"></span>
        <span>Sin conexión</span>
      </div>
    {:else if showConnectedPill}
      <div class="connectivity-pill online" transition:fade={{ duration: 150 }}>
        <span class="pulse-dot green"></span>
        <span>Conectado</span>
      </div>
    {/if}
    <span class="mono" style="font-size:13px; color: var(--xp); display: flex; align-items: center; gap: 8px;">
      <span>
        {#if $nextStageXP}
          {$totalXP.toLocaleString()}
          <span style="font-size:10px; color: var(--text-muted);">/ {$nextStageXP.toLocaleString()} xp</span>
        {:else}
          <span style="font-size:12px; font-weight: 700;">MAX</span>
        {/if}
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
    {#each navItems as { href, label, icon, status }}
      {@const active = $page.url.pathname === href || ($page.url.pathname.startsWith(href) && href !== '/')}
      <a {href} class="nav-item" class:active class:nav-dev={status === 'dev'} class:nav-placeholder={status === 'placeholder'} title={label}>
        <DynamicIcon name={icon} size={16} />
        {#if status === 'dev'}
          <span class="nav-dev-dot" title="Requiere Dev Mode"></span>
        {:else if status === 'placeholder'}
          <span class="nav-placeholder-badge">Pronto</span>
        {/if}
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
    <span style="color: var(--text-muted); cursor: pointer;" title="Click para notificación de prueba" on:click={() => { showNotification('Notificación de prueba - Info', 'info'); setTimeout(() => showNotification('Notificación de prueba - Success', 'success'), 600); setTimeout(() => showNotification('Notificación de prueba - Level up!', 'level'), 1200); }}>joidy v0.1</span>

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
<CommandPalette />
<Toast />
<TutorialOverlay />
{/if}

<style>
  .pwa-banner {
    display: flex;
    align-items: center;
    gap: 10px;
    background: color-mix(in srgb, var(--xp) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--xp) 30%, var(--border));
    padding: 4px 12px;
    border-radius: 99px;
    margin-left: 20px;
    font-size: 11px;
    color: var(--xp);
  }
  .pwa-actions {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-left: 4px;
  }
  .pwa-btn {
    background: none;
    border: none;
    color: currentColor;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2px 6px;
    border-radius: 4px;
    transition: background 0.2s;
  }
  .pwa-btn:hover {
    background: color-mix(in srgb, var(--xp) 20%, transparent);
  }
  .pwa-install {
    font-weight: 600;
    text-decoration: underline;
  }
  .pwa-dismiss {
    padding: 2px;
  }

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

  /* Connectivity Pill & Pulse Dot Styles */
  .connectivity-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: 99px;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    transition: all 0.2s ease-in-out;
    margin-right: 12px;
  }
  .connectivity-pill.offline {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: var(--error, #ef4444);
    box-shadow: 0 0 10px rgba(239, 68, 68, 0.1);
  }
  .connectivity-pill.online {
    background: rgba(34, 197, 94, 0.1);
    border: 1px solid rgba(34, 197, 94, 0.3);
    color: var(--success, #22c55e);
    box-shadow: 0 0 10px rgba(34, 197, 94, 0.1);
  }
  
  .pulse-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    display: inline-block;
  }
  .pulse-dot.red {
    background-color: var(--error, #ef4444);
    animation: red-pulse 1.5s infinite;
  }
  .pulse-dot.green {
    background-color: var(--success, #22c55e);
    animation: green-pulse 1.5s infinite;
  }
  
  @keyframes red-pulse {
    0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
    70% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
    100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
  }
  @keyframes green-pulse {
    0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }
    70% { box-shadow: 0 0 0 6px rgba(34, 197, 94, 0); }
    100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
  }

  .nav-dev-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--warning, #f59e0b);
    flex-shrink: 0;
    animation: dev-dot-pulse 2s infinite;
  }
  @keyframes dev-dot-pulse {
    0%, 100% { opacity: 0.6; }
    50%      { opacity: 1; box-shadow: 0 0 4px var(--warning, #f59e0b); }
  }
  .nav-item.nav-dev .tooltip::after {
    content: ' (dev)';
    font-size: 10px;
    color: var(--warning, #f59e0b);
  }

  .nav-placeholder-badge {
    font-size: 9px;
    line-height: 1;
    padding: 1px 4px;
    border-radius: 3px;
    background: var(--surface);
    color: var(--text-muted);
    border: 1px solid var(--border);
    font-style: italic;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .nav-item.nav-placeholder {
    opacity: 0.55;
  }
  .nav-item.nav-placeholder:hover {
    opacity: 0.8;
  }
</style>
