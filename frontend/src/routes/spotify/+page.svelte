<script lang="ts">
  // /spotify — Now Playing, library browser and playback controls (#45).
  //
  // Connection model: OAuth via GET /integrations/spotify/auth (popup +
  // status polling, same UX as Settings → Google) OR a manual access token
  // sent as X-Spotify-Token (advanced, for self-hosters without a Spotify
  // app). Data endpoints run silent; HTTP statuses map to dedicated UI
  // states — 401 reconnect, 403 Premium upsell, 404 no device, 429 rate limit.

  import { onMount, onDestroy } from 'svelte';
  import { t } from 'svelte-i18n';
  import Music from 'lucide-svelte/icons/music';
  import RefreshCw from 'lucide-svelte/icons/refresh-cw';
  import Unlink from 'lucide-svelte/icons/unlink';
  import Crown from 'lucide-svelte/icons/crown';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import NowPlayingCard from '$lib/components/spotify/NowPlayingCard.svelte';
  import TopCharts from '$lib/components/spotify/TopCharts.svelte';
  import PlaylistGrid from '$lib/components/spotify/PlaylistGrid.svelte';
  import RecentlyPlayed from '$lib/components/spotify/RecentlyPlayed.svelte';
  import { api, type SpotifyPlaybackState, type SpotifyStatus } from '$lib/api';
  import { showNotification } from '$lib/stores/notifications';
  import {
    getSpotifyTokenOverride,
    setSpotifyTokenOverride,
    spotifyErrorStatus,
  } from '$lib/utils/spotify';
  import { logger } from '$lib/utils/logger';

  type Notice = 'premium' | 'device' | 'rate' | 'expired' | null;

  let status = $state<SpotifyStatus | null>(null);
  let statusLoading = $state(true);
  let playback = $state<SpotifyPlaybackState | null>(null);
  let playbackAt = $state(0);
  let playbackLoading = $state(false);
  let playbackError = $state<number | null>(null);
  let sectionNotice = $state<Notice>(null);

  // Manual token override (advanced connect path).
  let tokenDraft = $state('');
  let token = $state('');

  // OAuth popup flow.
  let connecting = $state(false);
  let connectError = $state('');
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let pollTimeout: ReturnType<typeof setTimeout> | null = null;
  let destroyed = false;

  // Bumped to make list sections refetch (after connect / manual refresh).
  let sectionsKey = $state(0);

  const isConnected = $derived(!!status?.connected || !!token);
  const accountName = $derived(status?.account?.display_name || status?.account?.email || '');

  async function loadStatus() {
    statusLoading = true;
    try {
      status = await api.spotify.status(token || null);
    } catch (e) {
      logger.warn('Spotify status failed:', e);
      status = null;
    } finally {
      statusLoading = false;
    }
  }

  async function loadPlayback() {
    if (!isConnected) {
      playback = null;
      return;
    }
    playbackLoading = true;
    playbackError = null;
    try {
      playback = await api.spotify.currentlyPlaying(token || null);
      playbackAt = Date.now();
    } catch (e) {
      const code = spotifyErrorStatus(e);
      playbackError = code;
      playback = null;
      if (code === 401) sectionNotice = 'expired';
    } finally {
      playbackLoading = false;
    }
  }

  function refreshAll() {
    sectionsKey += 1;
    loadStatus();
    loadPlayback();
  }

  // ── OAuth popup + status polling (SettingsGoogle pattern) ─────────────────
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
      // The callback persists tokens server-side; poll until connected.
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
            refreshAll();
          }
        } catch {
          /* transient poll failure — keep polling */
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
    }
    status = null;
    playback = null;
    window.dispatchEvent(new CustomEvent('joidy:spotify-disconnected'));
    loadStatus();
  }

  function applyToken() {
    const value = tokenDraft.trim();
    setSpotifyTokenOverride(value);
    token = value;
    tokenDraft = '';
    if (value) {
      showNotification($t('spotify.tokenSaved'), 'success');
    } else {
      showNotification($t('spotify.tokenCleared'), 'info');
    }
    refreshAll();
  }

  // ── Playback actions shared by the browse sections ────────────────────────
  function mapPlayError(e: unknown) {
    const code = spotifyErrorStatus(e);
    if (code === 403) sectionNotice = 'premium';
    else if (code === 404) sectionNotice = 'device';
    else if (code === 429) sectionNotice = 'rate';
    else if (code === 401) sectionNotice = 'expired';
    else sectionNotice = 'device';
  }

  async function playContext(contextUri: string | null | undefined) {
    if (!contextUri) return;
    sectionNotice = null;
    try {
      await api.spotify.play({ context_uri: contextUri }, token || null);
      setTimeout(loadPlayback, 800);
    } catch (e) {
      mapPlayError(e);
    }
  }

  async function playUris(uris: string[], offsetPosition?: number | null) {
    const clean = uris.filter(Boolean);
    if (!clean.length) return;
    sectionNotice = null;
    try {
      await api.spotify.play(
        { uris: clean, offset_position: offsetPosition ?? null },
        token || null
      );
      setTimeout(loadPlayback, 800);
    } catch (e) {
      mapPlayError(e);
    }
  }

  onMount(() => {
    token = getSpotifyTokenOverride();
    tokenDraft = token;
    loadStatus().then(() => {
      if (isConnected) loadPlayback();
    });
  });

  onDestroy(() => {
    destroyed = true;
    stopPolling();
  });
</script>

<div class="spotify-page">
  <header class="sp-header">
    <div class="sp-title-wrap">
      <Music size={18} />
      <div>
        <h3>{$t('spotify.title')}</h3>
        <span class="caption">{$t('spotify.subtitle')}</span>
      </div>
    </div>
    <div class="sp-actions">
      {#if isConnected}
        {#if accountName}<span class="sp-account">{accountName}</span>{/if}
        <button class="chip-btn" onclick={refreshAll} disabled={playbackLoading} aria-label={$t('common.retry')}>
          <span class={playbackLoading ? 'spin' : ''}><RefreshCw size={13} /></span>
        </button>
        <button class="chip-btn danger" onclick={disconnect} disabled={connecting}>
          <Unlink size={13} /> {$t('spotify.disconnect')}
        </button>
      {:else if status?.configured !== false}
        <button class="chip-btn primary" onclick={startOAuth} disabled={connecting || statusLoading}>
          {connecting ? $t('spotify.connecting') : $t('spotify.connect')}
        </button>
      {/if}
    </div>
  </header>

  {#if connectError}
    <p class="sp-error">{connectError}</p>
  {/if}

  {#if !isConnected}
    <div class="sp-connect-card">
      <Music size={34} />
      {#if status && !status.configured}
        <p class="sp-connect-title">{$t('spotify.notConfiguredTitle')}</p>
        <p class="sp-connect-hint">{$t('spotify.notConfiguredHint')}</p>
      {:else}
        <p class="sp-connect-title">{$t('spotify.connectTitle')}</p>
        <p class="sp-connect-hint">{$t('spotify.connectHint')}</p>
        <button class="chip-btn primary big" onclick={startOAuth} disabled={connecting || statusLoading}>
          {connecting ? $t('spotify.connecting') : $t('spotify.connectWithSpotify')}
        </button>
        {#if connecting}<p class="caption">{$t('spotify.connectWaiting')}</p>{/if}
      {/if}

      <details class="sp-advanced">
        <summary>{$t('spotify.advancedToken')}</summary>
        <p class="hint">{$t('spotify.advancedTokenHint')}</p>
        <div class="sp-token-row">
          <input
            type="password"
            class="sp-input mono"
            placeholder="BQD…"
            aria-label={$t('spotify.advancedToken')}
            autocomplete="off"
            bind:value={tokenDraft}
          />
          <button class="chip-btn" onclick={applyToken} disabled={!tokenDraft.trim() && !token}>
            {$t('common.save')}
          </button>
          {#if token}<button class="chip-btn danger" onclick={() => { tokenDraft=''; applyToken(); }}>
            {$t('common.delete')}
          </button>{/if}
        </div>
      </details>
    </div>
  {:else}
    {#if sectionNotice}
      <div class="sp-notice" class:premium={sectionNotice === 'premium'} role="status">
        {#if sectionNotice === 'premium'}
          <Crown size={14} />
          <span>{$t('spotify.premiumRequired')}</span>
          <a href="https://www.spotify.com/premium/" target="_blank" rel="noopener noreferrer">
            {$t('spotify.learnMore')}
          </a>
        {:else if sectionNotice === 'rate'}
          <span>{$t('spotify.rateLimited')}</span>
        {:else if sectionNotice === 'expired'}
          <span>{$t('spotify.sessionExpired')}</span>
        {:else}
          <span>{$t('spotify.noDevice')}</span>
        {/if}
        <button class="sp-notice-close" onclick={() => (sectionNotice = null)} aria-label={$t('common.close')}>
          ×
        </button>
      </div>
    {/if}

    {#if playbackLoading && !playback}
      <div class="sp-card-skel"></div>
    {:else if playbackError === 401}
      <EmptyState title={$t('spotify.sessionExpiredTitle')} message={$t('spotify.sessionExpired')}>
        {#snippet icon()}<Music size={40} />{/snippet}
      </EmptyState>
    {:else}
      <NowPlayingCard playback={playback} fetchedAt={playbackAt} {token} onChanged={loadPlayback} />
    {/if}

    <div class="sp-grid">
      <RecentlyPlayed {token} onPlayUris={playUris} refreshKey={sectionsKey} />
      <div class="sp-grid-wide">
        <TopCharts {token} onPlayContext={playContext} onPlayUris={playUris} />
      </div>
      <PlaylistGrid {token} onPlayContext={playContext} onPlayUris={playUris} />
    </div>
  {/if}
</div>

<style>
  .spotify-page {
    display: flex;
    flex-direction: column;
    gap: 14px;
    max-width: 860px;
    margin: 0 auto;
    padding: 16px 8px 32px;
    width: 100%;
  }

  .sp-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .sp-title-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--accent);
  }

  .sp-title-wrap h3 {
    margin: 0;
    color: var(--text-primary);
    font-size: 18px;
  }

  .sp-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .sp-account {
    font-size: 12px;
    color: var(--text-secondary);
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .chip-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-secondary);
    font-size: 12px;
    padding: 6px 12px;
    border-radius: 999px;
    cursor: pointer;
    font-family: inherit;
  }

  .chip-btn:hover:not(:disabled) {
    border-color: var(--accent);
    color: var(--accent);
  }

  .chip-btn:disabled {
    opacity: 0.55;
    cursor: default;
  }

  .chip-btn.primary {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
  }

  .chip-btn.primary:hover:not(:disabled) {
    opacity: 0.9;
    color: #fff;
  }

  .chip-btn.danger:hover:not(:disabled) {
    border-color: var(--danger, #e05555);
    color: var(--danger, #e05555);
  }

  .chip-btn.big {
    padding: 9px 18px;
    font-size: 13px;
  }

  .spin {
    animation: sp-rot 0.9s linear infinite;
  }

  @keyframes sp-rot {
    to {
      transform: rotate(360deg);
    }
  }

  .sp-error {
    margin: 0;
    font-size: 12px;
    color: var(--danger, #e05555);
  }

  .sp-connect-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 36px 20px;
    border: 1px dashed var(--border);
    border-radius: var(--r-lg, 12px);
    color: var(--text-muted);
    text-align: center;
  }

  .sp-connect-title {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .sp-connect-hint {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
    max-width: 420px;
    line-height: 1.5;
  }

  .sp-advanced {
    margin-top: 8px;
    width: 100%;
    max-width: 460px;
    text-align: left;
  }

  .sp-advanced summary {
    cursor: pointer;
    font-size: 12px;
    color: var(--text-muted);
    list-style: none;
  }

  .sp-advanced summary::before {
    content: '▸ ';
  }

  .sp-advanced[open] summary::before {
    content: '▾ ';
  }

  .sp-advanced .hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.5;
    margin: 6px 0;
  }

  .sp-token-row {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .sp-input {
    flex: 1;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r, 8px);
    padding: 7px 10px;
    font-size: 12px;
    color: var(--text-primary);
    outline: none;
  }

  .sp-input:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  .sp-card-skel {
    height: 220px;
    border-radius: var(--r-lg, 12px);
    background: var(--elevated);
    animation: sp-pulse 1.2s ease-in-out infinite;
  }

  @keyframes sp-pulse {
    50% {
      opacity: 0.6;
    }
  }

  .sp-notice {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-secondary);
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r, 8px);
    padding: 9px 12px;
  }

  .sp-notice.premium {
    color: var(--xp, #e8b931);
    border-color: color-mix(in srgb, var(--xp, #e8b931) 40%, transparent);
  }

  .sp-notice a {
    color: var(--accent);
    margin-left: auto;
  }

  .sp-notice-close {
    margin-left: auto;
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 14px;
    padding: 0 4px;
  }

  .sp-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 14px;
    align-items: start;
  }

  .sp-grid-wide {
    grid-column: 1 / -1;
    min-width: 0;
  }

  .sp-grid-wide > :global(section) {
    height: 100%;
  }
</style>
