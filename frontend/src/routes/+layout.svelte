<script lang="ts">
  import '../app.css';
  import { browser } from '$app/env';
  import { page } from '$app/state';
  import { afterNavigate } from '$app/navigation';
  import { onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import { isOnline, wasOffline } from '$lib/stores/connection';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import CommandPalette from '$lib/components/CommandPalette.svelte';
  import FocusMode from '$lib/components/FocusMode.svelte';
  import Toast from '$lib/components/Toast.svelte';
  import StatusBarGitHub from '$lib/components/StatusBarGitHub.svelte';
  import Login from '$lib/components/Login.svelte';
  import SetupWizard from '$lib/components/SetupWizard.svelte';
  import { api, apiWsUrl, refreshAccessToken, type Goal, type PersonalStreak } from '$lib/api';
  import { session, isAuthenticated, getToken } from '$lib/stores/session';
  import { appHeaderTabs } from '$lib/stores/appHeader';

  // WAI-ARIA tabs pattern for the header tab strip: arrows/Home/End move
  // selection and focus together, regardless of which page owns the tabs.
  function onHeaderTabKeydown(e: KeyboardEvent) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
    const list = (e.currentTarget as HTMLElement).querySelectorAll<HTMLButtonElement>(
      'button[role="tab"]'
    );
    if (!list.length) return;
    e.preventDefault();
    e.stopPropagation();
    const idx = Array.from(list).findIndex((b) => b === document.activeElement);
    const cur = idx >= 0 ? idx : list.length - 1;
    let next = cur;
    if (e.key === 'ArrowRight') next = (cur + 1) % list.length;
    else if (e.key === 'ArrowLeft') next = (cur - 1 + list.length) % list.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = list.length - 1;
    list[next]?.click();
    list[next]?.focus();
  }
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
  import { initTimersEngine } from '$lib/stores/timers';
  import {
    accentColors,
    activeIconPack,
    use24HourClock,
    initTheme,
    devMode,
    themeMode,
  } from '$lib/stores/settings';
  import { getCachedData, setCachedData } from '$lib/utils/userSettings';
  import { createVaultSyncBurst } from '$lib/utils/vaultSyncBurst';
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
  import {
    deferredPrompt,
    showInstallBanner,
    isAppInstalled,
    waitingWorker,
    showUpdateBanner,
    initServiceWorkerRegistration,
    applyServiceWorkerUpdate,
  } from '$lib/stores/pwa';
  import { syncStore } from '$lib/stores/sync';
  import { toggle as toggleCommandPalette } from '$lib/stores/commandPalette';
  import ConflictResolutionModal from '$lib/components/ConflictResolutionModal.svelte';
  import OfflineIndicator from '$lib/components/OfflineIndicator.svelte';
  import { initOfflineSync } from '$lib/stores/offlineSync';
  import ShareAchievementModal from '$lib/components/ShareAchievementModal.svelte';
  import {
    initFocusModeConfig,
    queueNotificationIfActive,
    startFocusMode,
  } from '$lib/stores/focusMode';
  import {
    initUsageTracking,
    trackPageView,
    trackSessionStart,
    trackSessionEnd,
  } from '$lib/stores/usage';
  import {
    chunkUpdateAvailable,
    initChunkErrorRecovery,
    isChunkLoadError,
  } from '$lib/utils/chunkError';

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
    { href: '/streaks', label: $t('nav.streaks'), icon: 'Flame', status: 'ready' },
    { href: '/goals', label: $t('nav.goals'), icon: 'Target', status: 'ready' },
    { href: '/emails', label: $t('nav.emails'), icon: 'Mail', status: 'ready' },
    { href: '/gmail', label: $t('nav.gmail'), icon: 'Send', status: 'ready' },
    { href: '/contactos', label: $t('nav.contacts'), icon: 'Users', status: 'dev' },
    { href: '/calendar', label: $t('nav.calendar'), icon: 'Calendar', status: 'ready' },
    { href: '/timers', label: $t('nav.timers'), icon: 'AlarmClock', status: 'ready' },
    // Strava integration page (#44) — appended last to keep merges clean.
    { href: '/strava', label: $t('nav.strava'), icon: 'Activity', status: 'dev' },
    // #45 — Spotify integration (backend merged via #1448).
    { href: '/spotify', label: $t('nav.spotify'), icon: 'Music', status: 'dev' },
    // #1665 — analytics is pinned to the bottom of the rail, separated from
    // the primary nav group by a hairline divider (.nav-separator).
    { href: '/analytics', label: $t('nav.analytics'), icon: 'ChartColumn', status: 'ready', pinned: true },
  ] as { href: string; label: string; icon: string; status: NavItemStatus; pinned?: boolean }[];

  // Clock engine (#969): alarms must keep ticking wherever the user is in the
  // app. Only starts once authenticated — it pulls persisted alarms from the
  // API, which 401s (and force-logs-out) on the login screen otherwise.
  $: if (browser && $isAuthenticated) initTimersEngine();

  // Push subscription sync (#1546): the push endpoints require auth, so
  // running this on the login screen 401s → forced logout + a spurious
  // "Sesión expirada" toast for anyone who once granted permission.
  $: if (browser && $isAuthenticated) initPushNotifications();

  // Track page views on route changes (foreground-only, debounced in the
  // store). This runs in afterNavigate — a legacy `$:` statement never
  // re-runs on $app/state changes, so SPA navigations were invisible (#1305).
  afterNavigate((nav) => {
    if ($isAuthenticated && nav.to?.url.pathname) {
      trackPageView(nav.to.url.pathname);
    }
  });

  let settingsOpen = false;

  // Lazy-load the settings panel (~19 components across 9 sections) so it
  // splits out of the layout chunk and only downloads on first open —
  // mirrors the GoalEditor lazy pattern (#1544). A failed chunk import is
  // re-thrown so the chunk-error recovery owns the reload (#1459).
  let SettingsPanelComp: typeof import('$lib/components/SettingsPanel.svelte').default | null =
    null;
  let settingsChunkLoading = false;
  function ensureSettingsPanel() {
    if (SettingsPanelComp || settingsChunkLoading) return;
    settingsChunkLoading = true;
    import('$lib/components/SettingsPanel.svelte')
      .then((m) => (SettingsPanelComp = m.default))
      .catch((err) => {
        settingsOpen = false;
        throw err;
      })
      .finally(() => (settingsChunkLoading = false));
  }

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
  let setupCheckFailed = false;

  // A hung/failed setup-status request used to leave the app on an empty
  // viewport forever (no spinner, no error — #1459). The check now has a
  // hard timeout and a failure state with a retry action.
  const SETUP_CHECK_TIMEOUT_MS = 10_000;

  function checkSetupStatus() {
    checkingSetup = true;
    setupCheckFailed = false;
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      checkingSetup = false;
      setupCheckFailed = true;
      logger.error('[layout] setup-status check timed out');
    }, SETUP_CHECK_TIMEOUT_MS);

    api.config
      .setupStatus()
      .then((res) => {
        if (timedOut) return;
        clearTimeout(timer);
        needsSetup = res.needs_setup;
        checkingSetup = false;
      })
      .catch((err) => {
        if (timedOut) return;
        clearTimeout(timer);
        logger.error('Failed to check setup status:', err);
        checkingSetup = false;
        setupCheckFailed = true;
      });
  }

  onMount(() => {
    mounted = true;

    // Check setup status
    checkSetupStatus();

    accentColors.init();
    activeIconPack.init();
    themeMode.init();
    const cleanupTheme = initTheme();
    initPomodoroSettings();
    initFocusModeConfig();
    const cleanupKeyboard = initKeyboardNavigation();
    onboarding.init();
    achievements.init();
    devMode.init();
    const cleanupConnection = initConnectionStore();
    const cleanupOfflineSync = initOfflineSync();
    // Stale-chunk recovery (#1459): a deploy replaces hashed bundles while
    // open tabs still request the old ones — auto-reload once, then prompt.
    const cleanupChunkRecovery = initChunkErrorRecovery();

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

    // Coalesce WS-triggered note refetches: a bulk vault sync emits one
    // `vault_synced` message per file, and each forced loadNotes pays a full
    // notes.set() subscriber propagation on the main thread (#1494).
    let notesRefreshTimeout: any = null;
    const scheduleNotesRefresh = () => {
      if (notesRefreshTimeout) clearTimeout(notesRefreshTimeout);
      notesRefreshTimeout = setTimeout(() => {
        notesRefreshTimeout = null;
        loadNotes(undefined, true).catch(() => {});
      }, 1500);
    };

    // Same coalescing for stats refetches: `xp_gained`/`streak_updated` arrive
    // per gamification event (per tag per file during a bulk import), and each
    // raw loadStats paid a fetch plus a full routeCache localStorage write
    // (#1500).
    let statsRefreshTimeout: ReturnType<typeof setTimeout> | null = null;
    const scheduleStatsRefresh = () => {
      if (statsRefreshTimeout) clearTimeout(statsRefreshTimeout);
      statsRefreshTimeout = setTimeout(() => {
        statsRefreshTimeout = null;
        loadStats().catch(() => {});
      }, 2000);
    };

    // A bulk vault sync emits one `vault_synced` per file plus note_created and
    // xp_gained per event — per-message toasts cost a notifications.update +
    // Toast re-render + aria-atomic announce on the main thread each, enough to
    // freeze the tab mid-sync (#1500). While a burst is active, count files and
    // accumulate XP, then emit a single summary when it ends.
    const syncBurst = createVaultSyncBurst();
    const flushSyncBurst = () => {
      vaultSyncActive = false;
      const { files, xp } = syncBurst.reset();
      if (files > 1) {
        queueNotificationIfActive(
          $t('sync.syncedManyFromVault', { values: { count: files } }),
          'info'
        );
      }
      if (xp > 0) {
        queueNotificationIfActive(`¡+${xp} XP!`, 'level');
      }
    };

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

      // The WebSocket URL derives from the same resolved API base the REST
      // client uses (lib/api.ts → utils/apiBase.ts), so a port-fallback'd
      // API_PORT applies to the socket too (#1487).
      const wsUrl = apiWsUrl();

      // WS auth rides the Sec-WebSocket-Protocol handshake header instead of
      // a ?token= query param, which used to leak the JWT into proxy access
      // logs, browser history and console output (#1285, #1317). The server
      // answers the "bearer" marker to complete protocol negotiation.
      logger.info('[layout] Connecting to WebSocket:', wsUrl);
      const wsToken = getToken();
      ws = wsToken ? new WebSocket(wsUrl, ['bearer', wsToken]) : new WebSocket(wsUrl);

      ws.onopen = () => {
        logger.info('[layout] WebSocket connected');
        wsRetryDelay = 1000;
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          logger.info('[layout] WebSocket message received:', msg);

          if (msg.type === 'note_created') {
            // During a sync burst these fire per imported file — the summary
            // toast covers them; standalone creates keep their toast (#1500).
            if (!vaultSyncActive) {
              queueNotificationIfActive(`Nueva nota creada: "${msg.title}"`, 'success');
            }
            scheduleNotesRefresh();
          } else if (msg.type === 'note_updated') {
            if (!vaultSyncActive) {
              queueNotificationIfActive(`Nota actualizada: "${msg.title}"`, 'info');
            }
            scheduleNotesRefresh();
          } else if (msg.type === 'xp_gained') {
            // Mid-burst XP pings accumulate into the summary; outside a sync
            // they keep their instant toast (#1500).
            if (vaultSyncActive) {
              syncBurst.recordXp(Number(msg.xp) || 0);
            } else {
              queueNotificationIfActive(`¡+${msg.xp} XP!`, 'level');
            }
            scheduleStatsRefresh();
          } else if (msg.type === 'streak_updated') {
            queueNotificationIfActive(`¡Racha de ${msg.streak} días! 🔥`, 'info');
            scheduleStatsRefresh();
          } else if (msg.type === 'vault_synced') {
            // A note was synced from the Obsidian vault (#73). The first file
            // of a standalone sync keeps its per-file toast; files 2..N of a
            // burst collapse into the flushSyncBurst summary (#1500).
            if (syncBurst.recordFile() === 1 && !vaultSyncActive) {
              queueNotificationIfActive(
                $t('sync.syncedFromVault', { values: { title: msg.title } }),
                'info'
              );
            }
            scheduleNotesRefresh();
            vaultSyncActive = true;
            vaultSyncPulse = false;
            if (vaultSyncTimeout) clearTimeout(vaultSyncTimeout);
            vaultSyncTimeout = setTimeout(flushSyncBurst, 3000);
          } else if (msg.type === 'vault_sync_started') {
            // Flush any pending burst before starting a new one so its summary
            // isn't silently discarded.
            if (vaultSyncTimeout) clearTimeout(vaultSyncTimeout);
            vaultSyncTimeout = null;
            flushSyncBurst();
            vaultSyncActive = true;
          } else if (msg.type === 'vault_sync_complete') {
            scheduleNotesRefresh();
            if (vaultSyncTimeout) clearTimeout(vaultSyncTimeout);
            vaultSyncTimeout = null;
            flushSyncBurst();
            vaultSyncPulse = true;
            vaultSyncTimeout = setTimeout(() => {
              vaultSyncPulse = false;
            }, 2000);
          }
        } catch (e) {
          logger.error('[layout] Error parsing WebSocket message:', e);
        }
      };

      ws.onclose = (event) => {
        if (wsReconnectTimeout) clearTimeout(wsReconnectTimeout);
        const delay = Math.min(wsRetryDelay, 60000);
        logger.warn(`[layout] WebSocket connection closed, reconnecting in ${delay}ms...`);
        // 4001 = auth rejected at handshake. The access token may have expired
        // while the page was open — renew it silently so the reconnect picks
        // up a fresh credential via getToken() (#1285).
        if (event.code === 4001) {
          refreshAccessToken().finally(() => {
            wsReconnectTimeout = setTimeout(connectWS, delay);
          });
        } else {
          wsReconnectTimeout = setTimeout(connectWS, delay);
        }
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
    // Kit 3 emits service-worker.js as an ESM bundle, so registration must
    // use { type: 'module' } — a classic registration fails with a SyntaxError
    // and the SW never installs (#1310). The helper also wires the
    // "update available" banner → skipWaiting → controllerchange reload flow.
    if (import.meta.env.PROD && 'serviceWorker' in navigator) {
      initServiceWorkerRegistration();
    }

    const handleAppInstalled = () => {
      showNotification('¡Joidy instalado! Ahora puedes acceder desde tu escritorio.', 'success');
    };
    window.addEventListener('appinstalled', handleAppInstalled);

    // #1545 — the goals/streaks fetches are independent, so they run in
    // parallel, and concurrent triggers (focus + visibilitychange + the 60s
    // interval + joidy:streaks-updated can fire together) share one
    // in-flight run instead of stacking duplicate requests. Silent: this is
    // a background poll — failures are logged, not toasted.
    let footerStatsInflight: Promise<void> | null = null;

    const loadFooterStats = (force = false): Promise<void> => {
      if (document.visibilityState !== 'visible') return Promise.resolve();

      const now = Date.now();
      if (!force && now - lastFooterStatsFetch < 30000) return Promise.resolve();
      lastFooterStatsFetch = now;
      if (footerStatsInflight) return footerStatsInflight;

      const cachedGoals = getCachedData<Goal[]>('goals');
      const cachedStreaks = getCachedData<PersonalStreak[]>('streaks');
      if (cachedGoals) {
        // Untriaged inbox captures don't count as pending tasks (#1200)
        pendingTasks = cachedGoals.filter(
          (goal: Goal) => !goal.is_completed && goal.state !== 'INBOX'
        ).length;
      }
      if (cachedStreaks) {
        pendingStreaks = cachedStreaks.filter(
          (streak: PersonalStreak) => !streak.today_checked && !streak.is_archived
        ).length;
      }

      footerStatsInflight = Promise.all([
        api.goals
          .list(undefined, undefined, undefined, { silent: true })
          .then((goals) => {
            pendingTasks = goals.filter(
              (goal) => !goal.is_completed && goal.state !== 'INBOX'
            ).length;
            setCachedData('goals', goals);
          })
          .catch((e) => logger.error('[layout] goals list failed:', e)),
        api.personalStreaks
          .list({ include_archived: false }, { silent: true })
          .then((streaks) => {
            const newPendingStreaks = streaks.filter(
              (streak) => !streak.today_checked && !streak.is_archived
            ).length;
            pendingStreaks = newPendingStreaks;
            setCachedData('streaks', streaks);

            if (newPendingStreaks > 0 && !streaksNotified) {
              streaksNotified = true;
              showNotification(`Tienes ${newPendingStreaks} rachas pendientes hoy!`, 'info');
            }
          })
          .catch((e) => logger.error('[layout] personal streaks list failed:', e)),
      ])
        .then(() => {})
        .finally(() => {
          footerStatsInflight = null;
        });
      return footerStatsInflight;
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

    // Sync conflict polling is driven by the session lifecycle inside the
    // sync store itself (session.subscribe) so it also starts on in-session
    // logins, not just on mount (#1305).

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
      // Failed dynamic imports are owned by the chunk-error recovery — a
      // "new version" reload, not a generic error toast (#1459).
      if (isChunkLoadError(reason)) return;
      const msg = reason?.message || String(reason) || 'Promesa rechazada';
      console.error('[Unhandled rejection]', reason);
      showNotification(`Error inesperado: ${msg}`, 'error');
    };
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    const handleStreaksUpdated = () => {
      loadFooterStats().catch((e) => logger.error('[layout] footer stats refresh failed:', e));
    };

    const handleOpenSettings = () => {
      ensureSettingsPanel();
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
      if (notesRefreshTimeout) clearTimeout(notesRefreshTimeout);
      if (statsRefreshTimeout) clearTimeout(statsRefreshTimeout);
      if (pillTimeout) clearTimeout(pillTimeout);
      if (vaultSyncTimeout) clearTimeout(vaultSyncTimeout);
      if (cleanupTheme) cleanupTheme();
      if (cleanupKeyboard) cleanupKeyboard();
      if (cleanupConnection) cleanupConnection();
      if (cleanupOfflineSync) cleanupOfflineSync();
      cleanupChunkRecovery();
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
  <!-- Real loading indicator during SSR or the setup check — the old empty
       div left a blank viewport on hung requests (#1459). -->
  <div class="boot-screen" role="status" aria-live="polite">
    <div class="boot-spinner" aria-hidden="true"></div>
    <span class="boot-text">{$t('layout.loading')}</span>
  </div>
{:else if setupCheckFailed}
  <div class="boot-screen">
    <DynamicIcon name="TriangleAlert" size={28} color="var(--warning, #f59e0b)" />
    <span class="boot-text">{$t('layout.setupCheckFailed')}</span>
    <button class="btn btn-primary" onclick={checkSetupStatus}>{$t('common.retry')}</button>
  </div>
{:else if needsSetup}
  <SetupWizard />
  <Toast />
{:else if !$isAuthenticated}
  <Login />
  <Toast />
{:else}
  <div class="app-shell">
    <!-- Skip link: first tab stop on every route (#1268). The click handler
         moves focus explicitly because SPA hash navigation does not reliably
         focus the target. -->
    <a
      href="#main-content"
      class="skip-link"
      onclick={(e) => {
        e.preventDefault();
        document.getElementById('main-content')?.focus();
      }}>{$t('layout.skipToContent')}</a
    >

    <!-- Header -->
    <header class="app-header">
      <span class="logo mono">JOIDY</span>

      {#if $appHeaderTabs}
        <div
          class="header-tabs"
          role="tablist"
          aria-label={$appHeaderTabs.label}
          tabindex={-1}
          onkeydown={onHeaderTabKeydown}
        >
          {#each $appHeaderTabs.tabs as tab (tab.id)}
            {@const Icon = tab.icon}
            {#if tab.href}
              <a class="header-tab" href={tab.href}>
                <Icon size={14} /><span class="header-tab-label">{tab.label}</span>
              </a>
            {:else}
              <button
                type="button"
                class="header-tab"
                role="tab"
                class:active={$appHeaderTabs.activeId === tab.id}
                aria-selected={$appHeaderTabs.activeId === tab.id}
                tabindex={$appHeaderTabs.activeId === tab.id ? 0 : -1}
                onclick={() => $appHeaderTabs?.onselect(tab.id)}
              >
                <Icon size={14} /><span class="header-tab-label">{tab.label}</span>
                {#if tab.badge && tab.badge > 0}
                  <span class="header-tab-badge">{tab.badge}</span>
                {/if}
              </button>
            {/if}
          {/each}
        </div>
      {/if}

      {#if $showInstallBanner}
        <div class="pwa-banner" transition:fade={{ duration: 150 }}>
          <DynamicIcon name="CloudDownload" size={13} />
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

      {#if $showUpdateBanner && $waitingWorker}
        <div class="pwa-banner" transition:fade={{ duration: 150 }}>
          <DynamicIcon name="RefreshCw" size={13} />
          <span>{$t('pwa.updateAvailable')}</span>
          <div class="pwa-actions">
            <button class="pwa-btn pwa-install" onclick={() => applyServiceWorkerUpdate()}
              >{$t('pwa.update')}</button
            >
            <button
              class="pwa-btn pwa-dismiss"
              aria-label={$t('pwa.closeUpdateNotice')}
              onclick={() => showUpdateBanner.set(false)}
            >
              <DynamicIcon name="X" size={12} />
            </button>
          </div>
        </div>
      {/if}

      {#if !$appHeaderTabs}
        <div style="flex:1;"></div>
      {/if}

      {#if $appHeaderTabs?.trailing}
        <div class="header-trailing">
          {#each $appHeaderTabs.trailing as control, ci (ci)}
            {#if control.type === 'segmented'}
              <div class="header-segmented" role="group" aria-label={control.label}>
                {#each control.options as opt (opt.id)}
                  <button
                    type="button"
                    class="header-segmented-btn"
                    class:active={control.activeId === opt.id}
                    aria-pressed={control.activeId === opt.id}
                    title={opt.title}
                    onclick={() => control.onselect(opt.id)}>{opt.label}</button
                  >
                {/each}
              </div>
            {:else}
              {@const ActionIcon = control.icon}
              <button
                type="button"
                class="header-action"
                class:spinning={control.spinning}
                title={control.title}
                aria-label={control.title}
                disabled={control.disabled}
                onclick={control.onclick}
              >
                <ActionIcon size={14} />
              </button>
            {/if}
          {/each}
        </div>
      {/if}


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

      <!-- Connectivity Indicator — announced via a status live region (#1269) -->
      {#if !$isOnline}
        <div class="connectivity-pill offline" role="status" transition:fade={{ duration: 150 }}>
          <span class="pulse-dot red"></span>
          <span>{$t('status.offline')}</span>
        </div>
      {:else if showConnectedPill}
        <div class="connectivity-pill online" role="status" transition:fade={{ duration: 150 }}>
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
      {#each navItems as { href, label, icon, status, pinned }}
        {#if pinned && (status === 'ready' || $devMode)}
          <div class="nav-separator" aria-hidden="true"></div>
        {/if}
        {#if status === 'ready' || $devMode}
          {@const active =
            page.url.pathname === href || (page.url.pathname.startsWith(href) && href !== '/')}
          <a
            {href}
            class="nav-item"
            class:active
            class:nav-dev={status === 'dev'}
            class:nav-placeholder={status === 'placeholder'}
            title={label}
            aria-current={active ? 'page' : undefined}
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
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <main class="app-main" id="main-content" tabindex="-1">
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
          // intentional: one-shots target the notification store, not
          // component state — safe to outlive the layout (#1003)
          setTimeout(() => showNotification($t('layout.testNotifSuccess'), 'success'), 600);
          setTimeout(() => showNotification($t('layout.testNotifLevel'), 'level'), 1200);
        }}>joidy v{__APP_VERSION__}{#if $devMode && __GIT_SHA__}&nbsp;<span class="mono">({__GIT_SHA__})</span>{/if}</button
      >

      <div class="status-live" title={$t('layout.currentStatus')}>
        <span class="status-pill status-time mono">{currentTime}</span>
        <span class="status-pill status-date">{currentDate}</span>
        <span
          class="status-pill status-tasks"
          class:has-pending={pendingTasks > 0}
          class:is-completed={pendingTasks === 0}>{pendingTasks} {$t('common.tasks')}</span
        >
        {#if pendingStreaks > 0}
          <span
            class="status-pill status-streak-alert has-pending"
            title={$t('status.pendingStreaks')}
            role="status"
          >
            <DynamicIcon
              name="Flame"
              size={12}
              color="var(--accent-contrast, var(--warning, #f59e0b))"
            />
            <span>{pendingStreaks}</span>
          </span>
        {/if}
      </div>

      {#if !$appHeaderTabs}
        <div style="flex:1;"></div>
      {/if}

      <!-- Assigned GitHub PRs / Issues (#792) -->
      <StatusBarGitHub />

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

  {#if SettingsPanelComp}
    <svelte:component
      this={SettingsPanelComp}
      bind:open={settingsOpen}
      onClose={() => {
        settingsOpen = false;
        // Broadcast so mounted pages (e.g. notes) can refetch config after edits
        window.dispatchEvent(new CustomEvent('joidy:settings-closed'));
      }}
    />
  {/if}
  <CommandPalette />
  <FocusMode />
  <Toast />
  <OnboardingTour />
  <ConflictResolutionModal />
  <OfflineIndicator />
  <ShareAchievementModal />
{/if}

<!-- Stale-chunk prompt (#1459): shown when a lazy import failed after the
     guarded auto-reload was already spent. Top-level so it overlays every
     branch — boot screen, setup wizard, login and the app shell. -->
{#if $chunkUpdateAvailable}
  <div class="chunk-update-banner" role="alert" transition:fade={{ duration: 150 }}>
    <DynamicIcon name="RefreshCw" size={13} />
    <span>{$t('pwa.updateAvailable')}</span>
    <button class="btn btn-primary chunk-reload-btn" onclick={() => window.location.reload()}>
      {$t('common.reload')}
    </button>
    <button
      class="chunk-dismiss"
      aria-label={$t('common.close')}
      onclick={() => chunkUpdateAvailable.set(false)}
    >
      <DynamicIcon name="X" size={12} />
    </button>
  </div>
{/if}

<style>
  /* Boot screen (#1459) — real spinner + failure state instead of the old
     empty min-height div that rendered a permanently blank viewport. */
  .boot-screen {
    min-height: 100vh;
    background: var(--bg);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 14px;
    padding: 24px;
    text-align: center;
  }
  .boot-text {
    color: var(--text-muted);
    font-size: 13px;
    max-width: 32ch;
  }
  .boot-spinner {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: 2px solid var(--border);
    border-top-color: var(--xp);
    animation: boot-spin 0.9s linear infinite;
  }
  @keyframes boot-spin {
    to {
      transform: rotate(360deg);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .boot-spinner {
      animation: none;
      border-top-color: var(--border);
    }
  }

  /* Stale-chunk "new version" prompt (#1459) */
  .chunk-update-banner {
    position: fixed;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    z-index: var(--z-tooltip, 1000);
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--elevated);
    border: 1px solid var(--accent);
    border-radius: 999px;
    padding: 6px 8px 6px 14px;
    font-size: 12px;
    color: var(--text-primary);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    white-space: nowrap;
  }
  .chunk-reload-btn {
    padding: 4px 12px;
    font-size: 12px;
  }
  .chunk-dismiss {
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
  }
  .chunk-dismiss:hover {
    color: var(--text-primary);
    background: var(--surface-hover);
  }

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

  .header-tabs {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--s1);
    overflow-x: auto;
    scrollbar-width: none;
  }
  .header-tabs::-webkit-scrollbar {
    display: none;
  }
  .header-tab {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
    min-height: 30px;
    padding: 5px 12px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 13px;
    font-family: inherit;
    text-decoration: none;
    cursor: pointer;
    border-radius: var(--r);
    transition: all 0.2s ease;
    white-space: nowrap;
  }
  .header-tab:hover {
    background: var(--surface-hover);
    color: var(--text-primary);
  }
  .header-tab.active {
    background: var(--surface-active);
    color: var(--text-primary);
    font-weight: 500;
  }
  .header-tab:focus-visible {
    outline: 1px solid var(--xp);
    outline-offset: 2px;
  }
  .header-tab-badge {
    min-width: 18px;
    padding: 0 5px;
    border-radius: 999px;
    background: var(--accent);
    color: var(--accent-contrast-text, var(--bg));
    font-size: 10px;
    font-weight: 600;
    line-height: 16px;
    text-align: center;
    font-family: var(--font-mono);
  }
  .header-trailing {
    display: flex;
    align-items: center;
    gap: var(--s2);
  }
  .header-segmented {
    display: flex;
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
  }
  .header-segmented-btn {
    min-width: 40px;
    min-height: 26px;
    padding: 0 10px;
    border: none;
    border-left: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 600;
    font-family: var(--font-mono);
    cursor: pointer;
    transition: all 0.15s;
  }
  .header-segmented-btn:first-child {
    border-left: none;
  }
  .header-segmented-btn:hover {
    color: var(--text-secondary);
  }
  .header-segmented-btn.active {
    color: var(--xp);
    background: color-mix(in srgb, var(--xp) 12%, transparent);
  }
  .header-action {
    display: grid;
    place-items: center;
    width: 26px;
    height: 26px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }
  .header-action:hover {
    color: var(--text-primary);
    background: var(--surface-hover);
  }
  .header-action.spinning :global(svg) {
    animation: header-spin 0.9s linear infinite;
  }
  @keyframes header-spin {
    to {
      transform: rotate(360deg);
    }
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
    color: var(--text-muted);
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
    border-color: color-mix(in srgb, var(--accent-contrast, var(--xp)) 65%, var(--border));
    background: color-mix(in srgb, var(--accent-contrast, var(--xp)) 18%, transparent);
    color: var(--accent-contrast, var(--xp));
    font-weight: 600;
  }

  .status-tasks.has-pending,
  .status-streak-alert.has-pending {
    color: var(--accent-contrast, var(--warning, #f59e0b));
    border-color: color-mix(
      in srgb,
      var(--accent-contrast, var(--warning, #f59e0b)) 50%,
      var(--border)
    );
    background: color-mix(
      in srgb,
      var(--accent-contrast, var(--warning, #f59e0b)) 16%,
      transparent
    );
    font-weight: 600;
  }

  .status-tasks.is-completed {
    color: var(--success, #10b981);
    border-color: color-mix(in srgb, var(--success, #10b981) 35%, var(--border));
    background: color-mix(in srgb, var(--success, #10b981) 12%, transparent);
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

  /* Skip link — visually hidden until focused (#1268) */
  .skip-link {
    position: fixed;
    top: var(--s2);
    left: var(--s2);
    z-index: var(--z-tooltip);
    padding: var(--s2) var(--s4);
    background: var(--elevated);
    color: var(--text-primary);
    border: 1px solid var(--accent);
    border-radius: var(--r);
    font-size: 12px;
    font-family: var(--font-mono);
    text-decoration: none;
    opacity: 0;
    pointer-events: none;
    transform: translateY(-8px);
    transition:
      opacity var(--t-fast),
      transform var(--t-fast);
  }
  .skip-link:focus-visible {
    opacity: 1;
    pointer-events: auto;
    transform: translateY(0);
  }
</style>
