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
  import FocusMode from '$lib/components/FocusMode.svelte';
  import Toast from '$lib/components/Toast.svelte';
  import Login from '$lib/components/Login.svelte';
  import SetupWizard from '$lib/components/SetupWizard.svelte';
  import { api, type Goal, type PersonalStreak } from '$lib/api';
  import { session, isAuthenticated, getToken } from '$lib/stores/session';
  import {
    totalXP,
    loadStats,
    pingActivity,
    globalLevel,
    nextStageXP,
    showNotification,
  } from '$lib/stores/gamification';
  import { running, secondsLeft, phase } from '$lib/stores/pomodoro';
  import { initPomodoroSettings } from '$lib/stores/pomodoro';
  import {
    accentColors,
    activeIconPack,
    use24HourClock,
    initTheme,
    devMode,
    themeMode,
  } from '$lib/stores/settings';
  import { getCachedData, setCachedData } from '$lib/utils/userSettings';
  import { initKeyboardNavigation } from '$lib/utils/keyboardNavigation';
  import { initPushNotifications } from '$lib/push';
  import { logger } from '$lib/utils/logger';
  import { onboarding } from '$lib/stores/onboarding';
  import { locale as localeStore } from '$lib/stores/locale';
  import { initI18n } from '$lib/i18n';
  import { t } from 'svelte-i18n';
  import OnboardingTour from '$lib/components/OnboardingTour.svelte';
  import { achievements } from '$lib/stores/achievements';
  import { initConnectionStore } from '$lib/stores/connection';
  import { loadNotes } from '$lib/stores/notes';
  import { deferredPrompt, showInstallBanner, isAppInstalled } from '$lib/stores/pwa';
  import { syncStore } from '$lib/stores/sync';
  import { toggle as toggleCommandPalette } from '$lib/stores/commandPalette';
  import ConflictResolutionModal from '$lib/components/ConflictResolutionModal.svelte';
  import OfflineIndicator from '$lib/components/OfflineIndicator.svelte';
  import { initOfflineSync } from '$lib/stores/offlineSync';
  import ShareAchievementModal from '$lib/components/ShareAchievementModal.svelte';
  import { initFocusModeConfig, queueNotificationIfActive, startFocusMode } from '$lib/stores/focusMode';
  import {
    initUsageTracking,
    trackPageView,
    trackSessionStart,
    trackSessionEnd,
  } from '$lib/stores/usage';

  type NavItemStatus = 'ready' | 'dev' | 'placeholder';

  // Initialize i18n once — syncs svelte-i18n with the locale store (#370).
  initI18n();

  // Reactive so labels re-render when the locale changes.
  $: navItems = [
    { href: '/', label: $t('nav.home'), icon: 'Home', status: 'ready' },
    { href: '/notes', label: $t('nav.notes'), icon: 'BookOpen', status: 'ready' },
    { href: '/graph', label: $t('nav.graph'), icon: 'Network', status: 'dev' },
    { href: '/skills', label: $t('nav.skills'), icon: 'Zap', status: 'dev' },
    { href: '/ai', label: $t('nav.ai'), icon: 'Brain', status: 'dev' },
    { href: '/goals', label: $t('nav.goals'), icon: 'Target', status: 'ready' },
    { href: '/streaks', label: $t('nav.streaks'), icon: 'Flame', status: 'ready' },
  ] as { href: string; label: string; icon: string; status: NavItemStatus }[];

  // Track page views on route changes (foreground-only, debounced in the store).
  $: if (mounted && $isAuthenticated) {
    trackPageView($page.url.pathname);
  }

  let settingsOpen = false;
  let now = new Date();
  let pendingTasks = 0;
  let pendingStreaks = 0;
  let streaksNotified = false;
  let lastFooterStatsFetch = 0;
  let lastStatsLoad = 0;

  $: currentTime = now.toLocaleTimeString($localeStore, {
    hour: $use24HourClock ? '2-digit' : 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: !$use24HourClock,
  });

  $: currentDate = now.toLocaleDateString($localeStore, {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
  });

  let mounted = false;
  let needsSetup = false;
  let checkingSetup = true;

  onMount(() => {
    mounted = true;

    // Check setup status
    api.config
      .setupStatus()
      .then((res) => {
        needsSetup = res.needs_setup;
        checkingSetup = false;
      })
      .catch((err) => {
        logger.error('Failed to check setup status:', err);
        checkingSetup = false;
      });

    accentColors.init();
    activeIconPack.init();
    themeMode.init();
    const cleanupTheme = initTheme();
    initPomodoroSettings();
    initFocusModeConfig();
    const cleanupKeyboard = initKeyboardNavigation();
    initPushNotifications();
    onboarding.init();
    achievements.init();
    devMode.init();
    const cleanupConnection = initConnectionStore();
    const cleanupOfflineSync = initOfflineSync();

    // Internal usage tracking (#250) — only records while the app is in the
    // foreground. Starts a session on mount and ends it on cleanup.
    const cleanupUsage = initUsageTracking();
    if ($isAuthenticated) {
      trackSessionStart();
    }

    // First-use detection: start the onboarding tour for brand-new users.
    if ($isAuthenticated) {
      onboarding
        .shouldShowOnboarding()
        .then((show: boolean) => {
          if (show) onboarding.startTour();
        })
        .catch((e: unknown) => logger.warn('[layout] onboarding detection failed:', e));
    }

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
      // Derive the WebSocket URL from VITE_API_URL (which already reflects the
      // configured API_PORT) so the app works on non-default ports. Fall back
      // to the previous hostname:8000 behaviour when VITE_API_URL is unset.
      let wsHost = `${host}:8000`;
      const apiUrl = import.meta.env.VITE_API_URL as string | undefined;
      if (apiUrl) {
        try {
          const parsed = new URL(apiUrl);
          wsHost = `${parsed.hostname}:${parsed.port || (parsed.protocol === 'https:' ? '443' : '80')}`;
        } catch {
          wsHost = `${host}:8000`;
        }
      }
      const wsUrl = `${wsProto}//${wsHost}/ws${getToken() ? `?token=${encodeURIComponent(getToken()!)}` : ''}`;

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
            queueNotificationIfActive(`Nueva nota creada: "${msg.title}"`, 'success');
            loadNotes(undefined, true).catch(() => {});
          } else if (msg.type === 'note_updated') {
            queueNotificationIfActive(`Nota actualizada: "${msg.title}"`, 'info');
            loadNotes(undefined, true).catch(() => {});
          } else if (msg.type === 'xp_gained') {
            queueNotificationIfActive(`¡+${msg.xp} XP!`, 'level');
            loadStats().catch(() => {});
          } else if (msg.type === 'streak_updated') {
            queueNotificationIfActive(`¡Racha de ${msg.streak} días! 🔥`, 'info');
            loadStats().catch(() => {});
          } else if (msg.type === 'vault_synced') {
            // A note was synced from the Obsidian vault (#73).
            queueNotificationIfActive(
              $t('sync.syncedFromVault', { values: { title: msg.title } }),
              'info'
            );
            loadNotes(undefined, true).catch(() => {});
            vaultSyncActive = true;
            if (vaultSyncTimeout) clearTimeout(vaultSyncTimeout);
            vaultSyncTimeout = setTimeout(() => {
              vaultSyncActive = false;
            }, 3000);
          } else if (msg.type === 'vault_sync_started') {
            vaultSyncActive = true;
            if (vaultSyncTimeout) clearTimeout(vaultSyncTimeout);
          } else if (msg.type === 'vault_sync_complete') {
            loadNotes(undefined, true).catch(() => {});
            vaultSyncActive = false;
            vaultSyncPulse = true;
            if (vaultSyncTimeout) clearTimeout(vaultSyncTimeout);
            vaultSyncTimeout = setTimeout(() => {
              vaultSyncPulse = false;
            }, 2000);
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

    // Register service worker for PWA (production only).
    // In dev, SvelteKit does not emit a usable /service-worker.js (the
    // `$service-worker` virtual module references build-time assets that do
    // not exist at dev time), so registration fails with
    // "ServiceWorker script evaluation failed" on every page load. The SW
    // fetch handler would also intercept API calls and return 503 Offline
    // while the dev backend is restarting, breaking the dev workflow (#205).
    if (import.meta.env.PROD && 'serviceWorker' in navigator) {
      navigator.serviceWorker.register('/service-worker.js').catch((err) => {
        logger.warn('SW registration failed:', err);
      });
    }

    const handleAppInstalled = () => {
      showNotification('¡Joidy instalado! Ahora puedes acceder desde tu escritorio.', 'success');
    };
    window.addEventListener('appinstalled', handleAppInstalled);

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
        pendingStreaks = cachedStreaks.filter(
          (streak: PersonalStreak) => !streak.today_checked && !streak.is_archived
        ).length;
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
        const newPendingStreaks = streaks.filter(
          (streak) => !streak.today_checked && !streak.is_archived
        ).length;
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

    // Start sync conflict polling when authenticated
    if ($isAuthenticated) {
      syncStore.startPolling();
    }

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
        loadFooterStats(true).catch((e) =>
          logger.error('[layout] footer stats refresh failed:', e)
        );
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        if (Date.now() - lastFooterStatsFetch > 60000) {
          loadFooterStats(true).catch((e) =>
            logger.error('[layout] footer stats refresh failed:', e)
          );
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

    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      deferredPrompt.set(e);

      if (!$isAppInstalled) {
        const visits = parseInt(localStorage.getItem('joidy-visits') || '0');
        localStorage.setItem('joidy-visits', (visits + 1).toString());

        if (visits >= 1 && localStorage.getItem('joidy-pwa-dismissed') !== 'true') {
          showInstallBanner.set(true);
        }
      }
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);

    // Command palette toggle (Cmd/Ctrl+K)
    const handleCommandPaletteKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        toggleCommandPalette();
      }
    };
    window.addEventListener('keydown', handleCommandPaletteKey);

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
      window.removeEventListener('appinstalled', handleAppInstalled);
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('keydown', handleCommandPaletteKey);

      // Clean up WebSocket connection
      if (ws) {
        ws.onclose = null; // Prevent reconnect loop
        ws.close();
      }
      if (wsReconnectTimeout) clearTimeout(wsReconnectTimeout);
      if (pillTimeout) clearTimeout(pillTimeout);
      if (vaultSyncTimeout) clearTimeout(vaultSyncTimeout);
      if (cleanupTheme) cleanupTheme();
      if (cleanupKeyboard) cleanupKeyboard();
      if (cleanupConnection) cleanupConnection();
      if (cleanupOfflineSync) cleanupOfflineSync();
      if (cleanupUsage) cleanupUsage();
      if ($isAuthenticated) {
        trackSessionEnd();
      }
      syncStore.stopPolling();
    };
  });
  let showConnectedPill = false;
  let pillTimeout: any = null;

  // Vault sync indicator state (#73).
  let vaultSyncActive = false;
  let vaultSyncPulse = false;
  let vaultSyncTimeout: any = null;

  $: if ($isOnline && $wasOffline) {
    showConnectedPill = true;
    wasOffline.set(false);
    if (pillTimeout) clearTimeout(pillTimeout);
    pillTimeout = setTimeout(() => {
      showConnectedPill = false;
    }, 4000);
  }
</script>

{#if !mounted || checkingSetup}
  <!-- Render blank or loading during SSR or setup check -->
  <div style="min-height: 100vh; background: var(--bg);"></div>
{:else if needsSetup}
  <SetupWizard />
  <Toast />
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
          <span>{$t('pwa.installPrompt')}</span>
          <div class="pwa-actions">
            <button
              class="pwa-btn pwa-install"
              onclick={async () => {
                if ($deferredPrompt) {
                  $deferredPrompt.prompt();
                  const { outcome } = await $deferredPrompt.userChoice;
                  if (outcome === 'accepted') {
                    showInstallBanner.set(false);
                  }
                  deferredPrompt.set(null);
                }
              }}>{$t('common.install')}</button
            >
            <button
              class="pwa-btn pwa-dismiss"
              aria-label={$t('pwa.closeInstallNotice')}
              onclick={() => {
                showInstallBanner.set(false);
                localStorage.setItem('joidy-pwa-dismissed', 'true');
              }}
            >
              <DynamicIcon name="X" size={12} />
            </button>
          </div>
        </div>
      {/if}

      <div style="flex:1;"></div>

      <!-- Vault sync indicator (#73) -->
      {#if vaultSyncActive || vaultSyncPulse}
        <div
          class="vault-sync-indicator"
          class:syncing={vaultSyncActive}
          class:pulse={vaultSyncPulse}
          transition:fade={{ duration: 150 }}
          title={$t('sync.syncedFromVault', { values: { title: '' } }).trim() ||
            $t('sync.syncingVault')}
        >
          <DynamicIcon name="RefreshCw" size={12} />
          <span>{vaultSyncActive ? $t('sync.syncingVault') : $t('sync.syncedVault')}</span>
        </div>
      {/if}

      <!-- Connectivity Indicator -->
      {#if !$isOnline}
        <div class="connectivity-pill offline" transition:fade={{ duration: 150 }}>
          <span class="pulse-dot red"></span>
          <span>{$t('status.offline')}</span>
        </div>
      {:else if showConnectedPill}
        <div class="connectivity-pill online" transition:fade={{ duration: 150 }}>
          <span class="pulse-dot green"></span>
          <span>{$t('status.online')}</span>
        </div>
      {/if}
      <span
        class="mono"
        style="font-size:13px; color: var(--xp); display: flex; align-items: center; gap: 8px;"
      >
        <span>
          {#if $nextStageXP}
            {$totalXP.toLocaleString()}
            <span style="font-size:10px; color: var(--text-muted);"
              >/ {$nextStageXP.toLocaleString()} xp</span
            >
          {:else}
            <span style="font-size:12px; font-weight: 700;">MAX</span>
          {/if}
        </span>
        <span
          style="font-size:11px; color: var(--text-primary); background: var(--surface); border: 1px solid var(--border); padding: 2px 6px; border-radius: 4px;"
          >{$t('common.level')} {$globalLevel}</span
        >
      </span>
      <button
        class="btn btn-ghost btn-icon"
        title={$t('common.settings')}
        aria-label={$t('common.settings')}
        style="color: var(--text-muted);"
        onclick={() => window.dispatchEvent(new CustomEvent('joidy:open-settings'))}
      >
        <DynamicIcon name="Settings" size={14} />
      </button>
    </header>

    <!-- Sidebar -->
    <nav class="app-sidebar">
      {#each navItems as { href, label, icon, status }}
        {#if status === 'ready' || $devMode}
          {@const active =
            $page.url.pathname === href || ($page.url.pathname.startsWith(href) && href !== '/')}
          <a
            {href}
            class="nav-item"
            class:active
            class:nav-dev={status === 'dev'}
            class:nav-placeholder={status === 'placeholder'}
            title={label}
          >
            <DynamicIcon name={icon} size={16} />
            {#if status === 'dev'}
              <span class="nav-dev-dot" title={$t('status.requiresDevMode')}></span>
            {:else if status === 'placeholder'}
              <!-- Pronto badge removed -->
            {/if}
            <span class="tooltip">{label}</span>
          </a>
        {/if}
      {/each}
    </nav>

    <!-- Main content -->
    <main class="app-main">
      <slot />
    </main>

    <!-- Status bar -->
    <footer class="app-statusbar">
      <button
        type="button"
        class="statusbar-version-btn"
        title={$t('layout.testNotification')}
        aria-label={$t('layout.testNotification')}
        onclick={() => {
          showNotification($t('layout.testNotifInfo'), 'info');
          setTimeout(() => showNotification($t('layout.testNotifSuccess'), 'success'), 600);
          setTimeout(() => showNotification($t('layout.testNotifLevel'), 'level'), 1200);
        }}>joidy v{__APP_VERSION__}</button
      >

      <div class="status-live" title={$t('layout.currentStatus')}>
        <span class="status-pill status-time mono">{currentTime}</span>
        <span class="status-pill status-date">{currentDate}</span>
        <span class="status-pill status-tasks">{pendingTasks} {$t('common.tasks')}</span>
        {#if pendingStreaks > 0}
          <span class="status-pill status-streak-alert" title={$t('status.pendingStreaks')}>
            <DynamicIcon name="Flame" size={12} color="var(--xp)" />
            <span>{pendingStreaks}</span>
          </span>
        {/if}
      </div>

      <div style="flex:1;"></div>

      <!-- Mini global Pomodoro -->
      <div
        class="mini-pomo"
        class:is-running={$running}
        class:is-break={$phase !== 'work'}
        title={$t('layout.globalTimer')}
      >
        <span class="mono p-timer"
          >{String(Math.floor($secondsLeft / 60)).padStart(2, '0')}:{String(
            $secondsLeft % 60
          ).padStart(2, '0')}</span
        >
        <span class="p-dot" class:beat={$running}></span>
      </div>

      <!-- Focus Mode trigger -->
      <button
        class="mini-focus-btn"
        onclick={() => startFocusMode()}
        aria-label={$t('home.startFocusMode')}
        title={$t('home.focusMode')}
      >
        <DynamicIcon name="Target" size={14} />
      </button>
    </footer>
  </div>

  <SettingsPanel bind:open={settingsOpen} on:close={() => (settingsOpen = false)} />
  <CommandPalette />
  <FocusMode />
  <Toast />
  <OnboardingTour />
  <ConflictResolutionModal />
  <OfflineIndicator />
  <ShareAchievementModal />
{/if}

<style>
  .statusbar-version-btn {
    color: var(--text-muted);
    cursor: pointer;
    background: none;
    border: none;
    padding: 0;
    font: inherit;
  }

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
  .mini-pomo.is-running {
    color: var(--xp);
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 5%, transparent);
  }
  .mini-pomo.is-break {
    color: var(--success);
    border-color: var(--success);
  }
  .p-timer {
    font-size: 11px;
  }

  .mini-focus-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    margin-left: 6px;
    padding: 4px 8px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--elevated);
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--t-normal);
  }
  .mini-focus-btn:hover {
    color: var(--accent);
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 5%, transparent);
  }

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
    0%,
    100% {
      opacity: 0.3;
      transform: scale(0.9);
    }
    50% {
      opacity: 1;
      transform: scale(1.1);
      box-shadow: 0 0 5px currentColor;
    }
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
    background: color-mix(in srgb, var(--error) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--error) 30%, transparent);
    color: var(--error);
    box-shadow: 0 0 10px color-mix(in srgb, var(--error) 10%, transparent);
  }
  .connectivity-pill.online {
    background: color-mix(in srgb, var(--success) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--success) 30%, transparent);
    color: var(--success);
    box-shadow: 0 0 10px color-mix(in srgb, var(--success) 10%, transparent);
  }

  .pulse-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    display: inline-block;
  }
  .pulse-dot.red {
    background-color: var(--error);
    animation: red-pulse 1.5s infinite;
  }
  .pulse-dot.green {
    background-color: var(--success, #22c55e);
    animation: green-pulse 1.5s infinite;
  }

  /* Vault sync indicator (#73) */
  .vault-sync-indicator {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: 99px;
    margin-right: 12px;
    background: color-mix(in srgb, var(--accent, var(--xp)) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--accent, var(--xp)) 30%, transparent);
    color: var(--accent, var(--xp));
    transition: all 0.2s ease-in-out;
  }
  .vault-sync-indicator.syncing :global(svg) {
    animation: vault-spin 1s linear infinite;
  }
  .vault-sync-indicator.pulse {
    background: color-mix(in srgb, var(--success, #22c55e) 10%, transparent);
    border-color: color-mix(in srgb, var(--success, #22c55e) 30%, transparent);
    color: var(--success, #22c55e);
  }
  @keyframes vault-spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  @keyframes red-pulse {
    0% {
      box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
    }
    70% {
      box-shadow: 0 0 0 6px rgba(239, 68, 68, 0);
    }
    100% {
      box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
    }
  }
  @keyframes green-pulse {
    0% {
      box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4);
    }
    70% {
      box-shadow: 0 0 0 6px rgba(34, 197, 94, 0);
    }
    100% {
      box-shadow: 0 0 0 0 rgba(34, 197, 94, 0);
    }
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
    0%,
    100% {
      opacity: 0.6;
    }
    50% {
      opacity: 1;
      box-shadow: 0 0 4px var(--warning, #f59e0b);
    }
  }
  .nav-item.nav-dev .tooltip::after {
    content: ' (dev)';
    font-size: 10px;
    color: var(--warning, #f59e0b);
  }

  .nav-item.nav-placeholder {
    opacity: 0.55;
  }
  .nav-item.nav-placeholder:hover {
    opacity: 0.8;
  }
</style>
