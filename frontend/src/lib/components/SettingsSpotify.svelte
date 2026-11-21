<script lang="ts">
  // Spotify row for Settings → Integraciones (#45).
  //
  // Mirrors SettingsGoogle: OAuth popup + status polling, disconnect with the
  // backend-provided manage_apps_url (Spotify has no token-revoke endpoint),
  // and an advanced manual-token field backed by the same localStorage
  // override the /spotify page uses. Dispatches joidy:spotify-* events so the
  // dashboard widget refreshes without a reload.

  import { onMount, onDestroy } from 'svelte';
  import { t } from 'svelte-i18n';
  import Music from 'lucide-svelte/icons/music';
  import ExternalLink from 'lucide-svelte/icons/external-link';
  import { api, type SpotifyStatus } from '$lib/api';
  import { showNotification } from '$lib/stores/notifications';
  import {
    getSpotifyTokenOverride,
    setSpotifyTokenOverride,
  } from '$lib/utils/spotify';
  import { logger } from '$lib/utils/logger';

  let status = $state<SpotifyStatus | null>(null);
  let connecting = $state(false);
  let connectError = $state('');
  let disconnecting = $state(false);
  let showAdvanced = $state(false);
  let tokenDraft = $state('');
  let token = $state('');

  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let pollTimeout: ReturnType<typeof setTimeout> | null = null;
  let destroyed = false;

  const isConnected = $derived(!!status?.connected || !!token);
  const accountLabel = $derived(
    status?.account?.display_name || status?.account?.email || ''
  );

  onMount(async () => {
    token = getSpotifyTokenOverride();
    tokenDraft = token;
    await checkStatus();
  });

  onDestroy(() => {
    destroyed = true;
    stopPolling();
  });

  async function checkStatus() {
    try {
      status = await api.spotify.status(token || null);
    } catch (e) {
      logger.warn('Spotify status check failed:', e);
      status = null;
    }
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    if (pollTimeout) {
      clearTimeout(pollTimeout);
      pollTimeout = null;
    }
  }

  async function startOAuth() {
    connecting = true;
    connectError = '';
    try {
      const data = await api.spotify.authUrl();
      window.open(data.url, '_blank', 'noopener,noreferrer');
      pollTimer = setInterval(async () => {
        if (destroyed || pollTimer === null) return;
        try {
          const s = await api.spotify.status(token || null);
          status = s;
          if (s.connected) {
            stopPolling();
            connecting = false;
            showNotification($t('spotify.connectedOk'), 'success');
            window.dispatchEvent(new CustomEvent('joidy:spotify-connected'));
          }
        } catch {
          /* transient — keep polling */
        }
      }, 3000);
      pollTimeout = setTimeout(() => {
        stopPolling();
        connecting = false;
        if (!destroyed && !status?.connected) {
          connectError = $t('spotify.connectTimeout');
        }
      }, 300000);
    } catch (e: any) {
      connectError = e?.message || $t('spotify.connectError');
      connecting = false;
    }
  }

  async function disconnect() {
    disconnecting = true;
    stopPolling();
    connecting = false;
    try {
      const res = await api.spotify.disconnect();
      if (res?.manage_apps_url) {
        showNotification($t('spotify.disconnectedNote'), 'info', res.manage_apps_url);
      } else {
        showNotification($t('spotify.disconnected'), 'info');
      }
    } catch (e: any) {
      showNotification(e?.message || $t('spotify.disconnectError'), 'error');
    } finally {
      disconnecting = false;
    }
    status = null;
    window.dispatchEvent(new CustomEvent('joidy:spotify-disconnected'));
  }

  function applyToken() {
    const value = tokenDraft.trim();
    setSpotifyTokenOverride(value);
    token = value;
    tokenDraft = value;
    showNotification(value ? $t('spotify.tokenSaved') : $t('spotify.tokenCleared'), value ? 'success' : 'info');
    window.dispatchEvent(
      new CustomEvent(value ? 'joidy:spotify-connected' : 'joidy:spotify-disconnected')
    );
  }
</script>

<!-- Spotify Integration -->
<div class="row">
  <div class="row-label">
    <Music size={13} />
    <span>Spotify</span>
    {#if isConnected}<span class="configured-badge">✓</span>{/if}
  </div>
  {#if connecting}
    <span class="mono" style="font-size:12px; color: var(--text-muted);">
      {$t('spotify.connectingShort')}
    </span>
  {:else if isConnected}
    <div style="display:flex; align-items:center; gap:8px;">
      {#if accountLabel}
        <span class="mono" style="font-size:12px; color: var(--xp);">{accountLabel}</span>
      {/if}
      <button class="link-btn disconnect-btn" onclick={disconnect} disabled={disconnecting}>
        {$t('spotify.disconnect')}
      </button>
    </div>
  {:else if status?.configured}
    <button class="link-btn" onclick={startOAuth} disabled={connecting}>
      {$t('spotify.connect')}
    </button>
  {:else if status}
    <button
      class="link-btn"
      onclick={() => {
        showAdvanced = true;
        showNotification($t('spotify.notConfiguredHint'), 'info');
      }}
    >
      {$t('spotify.configure')}
    </button>
  {:else}
    <button class="link-btn" onclick={checkStatus}>{$t('common.retry')}</button>
  {/if}
</div>

{#if connectError}
  <p class="hint" style="color:var(--danger); margin-top: 4px;">{connectError}</p>
{/if}

{#if !isConnected}
  <div style="margin-top: 8px;">
    <button
      type="button"
      class="toggle"
      style="font-size: 10px; padding: 3px 8px;"
      aria-expanded={showAdvanced}
      onclick={() => (showAdvanced = !showAdvanced)}
    >
      <ExternalLink size={11} />
      <span>{$t('spotify.advancedToken')}</span>
    </button>
  </div>
{/if}

{#if showAdvanced && !isConnected}
  <div
    style="margin-top: 8px; display: flex; flex-direction: column; gap: 6px; border-left: 2px solid var(--border); padding-left: 12px; margin-left: 4px;"
  >
    <p class="hint" style="margin: 0;">{$t('spotify.advancedTokenHint')}</p>
    <div style="display: flex; gap: 8px; align-items: center;">
      <input
        type="password"
        class="setting-input mono"
        style="font-size: 12px; padding: 6px 10px; flex: 1;"
        placeholder="BQD…"
        aria-label={$t('spotify.advancedToken')}
        autocomplete="off"
        bind:value={tokenDraft}
      />
      <button class="link-btn" style="white-space: nowrap;" onclick={applyToken}>
        {$t('common.save')}
      </button>
      {#if token}
        <button class="link-btn disconnect-btn" style="white-space: nowrap;" onclick={() => { tokenDraft = ''; applyToken(); }}>
          {$t('common.delete')}
        </button>
      {/if}
    </div>
  </div>
{/if}

<style>
  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 0;
  }

  .row-label {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 12px;
    color: var(--text-secondary);
  }

  .hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.6;
    margin-top: 8px;
  }

  .setting-input {
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 6px 10px;
    font-size: 11px;
    color: var(--text-primary);
    outline: none;
    transition: border-color var(--t-fast);
    width: 100%;
  }
  .setting-input:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 2px;
  }

  .configured-badge {
    font-size: 10px;
    color: var(--success);
    margin-left: 4px;
  }

  .toggle {
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 3px 8px;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
    transition: border-color var(--t-fast);
  }

  .toggle:hover {
    border-color: var(--text-muted);
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
  }
  .link-btn:hover {
    opacity: 0.9;
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
