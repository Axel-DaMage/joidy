<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { resolve } from '$app/paths';
  import { api } from '$lib/api';
  import { showNotification } from '$lib/stores/notifications';
  import { logger } from '$lib/utils/logger';
  import { t } from 'svelte-i18n';
  import type { StravaAthleteSummary } from '$lib/strava/types';

  /**
   * Strava connection row for Settings → Integraciones (#44).
   *
   * Unlike Google there are no UI-editable credentials: STRAVA_CLIENT_ID /
   * SECRET / REDIRECT_URI come from .env, so an unconfigured install shows a
   * hint instead of a credential form. The OAuth callback persists tokens
   * server-side and renders a self-closing popup — we poll /status until
   * `connected` flips (same pattern as SettingsGoogle).
   */

  let configured = $state(false);
  let connected = $state(false);
  let athlete = $state<StravaAthleteSummary | null>(null);
  let connecting = $state(false);
  let disconnecting = $state(false);
  let statusError = $state('');
  let checked = $state(false);

  let pollInterval: ReturnType<typeof setInterval> | null = null;
  let pollTimeout: ReturnType<typeof setTimeout> | null = null;
  let destroyed = false;

  onMount(async () => {
    await checkStatus();
  });

  onDestroy(() => {
    destroyed = true;
    stopPolling();
  });

  async function checkStatus(): Promise<void> {
    try {
      const status = await api.strava.status();
      configured = status.configured;
      connected = status.connected;
      athlete = status.athlete;
      statusError = '';
    } catch (e) {
      logger.warn('strava status check failed', e);
      statusError = e instanceof Error ? e.message : String(e);
    } finally {
      checked = true;
    }
  }

  function stopPolling(): void {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    if (pollTimeout) {
      clearTimeout(pollTimeout);
      pollTimeout = null;
    }
  }

  function athleteName(): string {
    if (!athlete) return '';
    const full = [athlete.firstname, athlete.lastname].filter(Boolean).join(' ').trim();
    return full || athlete.username || '';
  }

  async function startConnect(): Promise<void> {
    connecting = true;
    statusError = '';
    try {
      const data = await api.strava.authUrl();
      window.open(data.url, '_blank', 'noopener,noreferrer');
      // The callback persists tokens server-side; poll until status flips.
      pollInterval = setInterval(async () => {
        await checkStatus();
        if (destroyed || pollInterval === null) return;
        if (connected) {
          stopPolling();
          connecting = false;
          showNotification($t('strava.settings.connectedToast'), 'success');
        }
      }, 3000);
      pollTimeout = setTimeout(() => {
        stopPolling();
        connecting = false;
        if (!connected && !destroyed) {
          statusError = $t('strava.settings.connectTimeout');
        }
      }, 300000);
    } catch (e) {
      statusError = e instanceof Error ? e.message : String(e);
      connecting = false;
    }
  }

  async function disconnect(): Promise<void> {
    stopPolling();
    connecting = false;
    disconnecting = true;
    try {
      await api.strava.disconnect();
      connected = false;
      athlete = null;
      showNotification($t('strava.settings.disconnectedToast'), 'info');
    } catch (e) {
      statusError = e instanceof Error ? e.message : String(e);
    } finally {
      disconnecting = false;
    }
  }
</script>

<div class="row strava-settings-row">
  <div class="row-label">
    <span>Strava</span>
    {#if connected}
      <span class="configured-badge">✓</span>
    {:else if configured}
      <span class="configured-badge muted">+ {$t('strava.settings.configuredBadge')}</span>
    {/if}
  </div>

  <div class="strava-actions">
    {#if !checked}
      <span class="mono status-text">{$t('strava.settings.checking')}</span>
    {:else if connecting}
      <span class="mono status-text">{$t('strava.settings.connecting')}</span>
    {:else if connected}
      <span class="athlete-name" title={athleteName()}>
        {athleteName() || $t('strava.settings.connected')}
      </span>
      <a class="link-btn ghost" href={resolve('/strava')}>{$t('strava.settings.openPage')}</a>
      <button class="link-btn disconnect-btn" onclick={disconnect} disabled={disconnecting}>
        {disconnecting ? $t('strava.settings.disconnecting') : $t('strava.settings.disconnect')}
      </button>
    {:else if configured}
      <button class="link-btn" onclick={startConnect}>
        {$t('strava.settings.connect')}
      </button>
    {:else}
      <span class="mono status-text hint-text" title="STRAVA_CLIENT_ID · STRAVA_CLIENT_SECRET · STRAVA_REDIRECT_URI">
        {$t('strava.settings.notConfigured')}
      </span>
    {/if}
  </div>

  {#if statusError}
    <p class="hint error">{statusError}</p>
  {/if}
</div>

<style>
  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 0;
    flex-wrap: wrap;
    gap: 6px;
  }
  .row-label {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 12px;
    color: var(--text-secondary);
  }
  .strava-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .status-text {
    font-size: 11px;
    color: var(--text-muted);
  }
  .hint-text {
    max-width: 260px;
  }
  .athlete-name {
    font-size: 11px;
    color: var(--text-primary);
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .hint {
    width: 100%;
    font-size: 11px;
    color: var(--text-muted);
    margin: 2px 0 0;
  }
  .hint.error {
    color: var(--danger);
  }
  .configured-badge {
    font-size: 10px;
    color: var(--success);
    margin-left: 4px;
  }
  .configured-badge.muted {
    color: var(--text-muted);
  }
  .link-btn {
    background: var(--accent);
    color: white;
    border: none;
    padding: 6px 12px;
    border-radius: var(--r);
    font-size: 11px;
    cursor: pointer;
    font-family: var(--font-mono);
    text-decoration: none;
    display: inline-flex;
    align-items: center;
  }
  .link-btn:hover {
    opacity: 0.9;
  }
  .link-btn.ghost {
    background: transparent;
    color: var(--accent);
    border: 1px solid var(--border);
  }
  .link-btn.ghost:hover {
    border-color: var(--accent);
  }
  .disconnect-btn {
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--border);
  }
  .disconnect-btn:hover {
    background: var(--hover);
    border-color: var(--text-muted);
    color: var(--text-primary);
  }
</style>
