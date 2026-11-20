<script lang="ts">
  // Compact Spotify now-playing widget for the dashboard (#45).
  //
  // Self-contained: resolves connection status (OAuth or manual token), then
  // polls /currently-playing every 30 s while mounted and the tab is visible.
  // All fetches are silent and failures degrade to a compact connect/empty
  // state — the dashboard never blocks on Spotify.

  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { t } from 'svelte-i18n';
  import Music from 'lucide-svelte/icons/music';
  import Play from 'lucide-svelte/icons/play';
  import Pause from 'lucide-svelte/icons/pause';
  import SkipForward from 'lucide-svelte/icons/skip-forward';
  import SkipBack from 'lucide-svelte/icons/skip-back';
  import ExternalLink from 'lucide-svelte/icons/external-link';
  import Crown from 'lucide-svelte/icons/crown';
  import { api, type SpotifyPlaybackState, type SpotifyStatus } from '$lib/api';
  import {
    getSpotifyTokenOverride,
    spotifyErrorStatus,
  } from '$lib/utils/spotify';
  import { logger } from '$lib/utils/logger';

  const POLL_MS = 30_000;

  let status = $state<SpotifyStatus | null>(null);
  let playback = $state<SpotifyPlaybackState | null>(null);
  let loading = $state(true);
  let notice = $state<'premium' | 'expired' | null>(null);
  let busy = $state(false);
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let destroyed = false;

  const token = getSpotifyTokenOverride();
  const isConnected = $derived(!!status?.connected || !!token);
  const track = $derived(playback?.track ?? null);

  async function refreshPlayback() {
    try {
      playback = await api.spotify.currentlyPlaying(token || null);
    } catch (e) {
      const code = spotifyErrorStatus(e);
      if (code === 401) notice = 'expired';
      else if (code === 403) notice = 'premium';
      playback = null;
    }
  }

  async function refresh() {
    try {
      status = await api.spotify.status(token || null);
      if (isConnected) {
        await refreshPlayback();
      } else {
        playback = null;
      }
    } catch (e) {
      logger.warn('Spotify widget status failed:', e);
    } finally {
      loading = false;
    }
  }

  function schedulePoll() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(() => {
      if (destroyed || document.hidden || !isConnected) return;
      refreshPlayback();
    }, POLL_MS);
  }

  onMount(() => {
    refresh().finally(schedulePoll);
    window.addEventListener('joidy:spotify-connected', onSpotifyEvent);
    window.addEventListener('joidy:spotify-disconnected', onSpotifyEvent);
    document.addEventListener('visibilitychange', onVisibility);
  });

  onDestroy(() => {
    destroyed = true;
    if (pollTimer) clearInterval(pollTimer);
    window.removeEventListener('joidy:spotify-connected', onSpotifyEvent);
    window.removeEventListener('joidy:spotify-disconnected', onSpotifyEvent);
    document.removeEventListener('visibilitychange', onVisibility);
  });

  function onSpotifyEvent() {
    loading = true;
    refresh();
  }

  function onVisibility() {
    if (!document.hidden && isConnected) refreshPlayback();
  }

  async function control(kind: 'prev' | 'play' | 'next') {
    if (busy) return;
    busy = true;
    const deviceId = playback?.device?.id ?? null;
    try {
      if (kind === 'prev') await api.spotify.previous(deviceId, token || null);
      else if (kind === 'next') await api.spotify.next(deviceId, token || null);
      else if (playback?.is_playing) await api.spotify.pause(deviceId, token || null);
      else await api.spotify.play({ device_id: deviceId }, token || null);
      notice = null;
      setTimeout(refreshPlayback, 800);
    } catch (e) {
      const code = spotifyErrorStatus(e);
      if (code === 403) notice = 'premium';
      else if (code === 401) notice = 'expired';
    } finally {
      busy = false;
    }
  }
</script>

<div class="sp-widget">
  <div class="sp-head">
    <span class="sp-title"><Music size={12} /> Spotify</span>
    <button
      class="sp-open"
      onclick={() => goto('/spotify')}
      title={$t('spotify.openPage')}
      aria-label={$t('spotify.openPage')}
    >
      <ExternalLink size={11} />
    </button>
  </div>

  {#if loading}
    <div class="sp-skel"></div>
  {:else if !isConnected}
    <button class="sp-connect" onclick={() => goto('/spotify')}>
      <Music size={16} />
      <span>{$t('spotify.connectShort')}</span>
    </button>
  {:else if notice === 'expired'}
    <button class="sp-connect" onclick={() => goto('/spotify')}>
      <Music size={16} />
      <span>{$t('spotify.reconnect')}</span>
    </button>
  {:else if track}
    <div class="sp-body">
      <div class="sp-art">
        {#if track.album_image_url}
          <img src={track.album_image_url} alt="" loading="lazy" />
        {:else}
          <Music size={16} />
        {/if}
        {#if playback?.is_playing}<span class="sp-live"></span>{/if}
      </div>
      <div class="sp-info">
        <span class="sp-track">{track.name ?? '—'}</span>
        <span class="sp-artist">{track.artist_names}</span>
        {#if notice === 'premium'}
          <span class="sp-premium"><Crown size={10} /> {$t('spotify.premiumShort')}</span>
        {/if}
      </div>
      <div class="sp-controls">
        <button class="sp-btn" onclick={() => control('prev')} disabled={busy} aria-label={$t('common.previous')}>
          <SkipBack size={14} />
        </button>
        <button class="sp-btn sp-btn-main" onclick={() => control('play')} disabled={busy}
          aria-label={playback?.is_playing ? $t('spotify.pause') : $t('spotify.play')}>
          {#if busy}<span class="sp-spinner"></span>{:else if playback?.is_playing}<Pause size={14} />{:else}<Play size={14} />{/if}
        </button>
        <button class="sp-btn" onclick={() => control('next')} disabled={busy} aria-label={$t('common.next')}>
          <SkipForward size={14} />
        </button>
      </div>
    </div>
  {:else}
    <div class="sp-idle">
      <Music size={16} />
      <span>{$t('spotify.nothingPlayingShort')}</span>
    </div>
  {/if}
</div>

<style>
  .sp-widget {
    display: flex;
    flex-direction: column;
    gap: 8px;
    width: 100%;
  }

  .sp-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .sp-title {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .sp-open {
    display: inline-flex;
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    padding: 2px;
    border-radius: 4px;
  }

  .sp-open:hover {
    color: var(--accent);
  }

  .sp-skel {
    height: 52px;
    border-radius: var(--r, 8px);
    background: var(--elevated);
    animation: sp-pulse 1.2s ease-in-out infinite;
  }

  @keyframes sp-pulse {
    50% {
      opacity: 0.5;
    }
  }

  .sp-connect {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border: 1px dashed var(--border);
    background: transparent;
    color: var(--text-secondary);
    font-size: 12px;
    padding: 12px 8px;
    border-radius: var(--r, 8px);
    cursor: pointer;
    width: 100%;
  }

  .sp-connect:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .sp-idle {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: var(--text-muted);
    font-size: 12px;
    padding: 14px 8px;
  }

  .sp-body {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .sp-art {
    position: relative;
    width: 42px;
    height: 42px;
    border-radius: 6px;
    overflow: hidden;
    background: var(--elevated);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .sp-art img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .sp-live {
    position: absolute;
    bottom: 3px;
    right: 3px;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--success, #4caf50);
  }

  .sp-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .sp-track {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .sp-artist {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .sp-premium {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: 10px;
    color: var(--xp, #e8b931);
    margin-top: 2px;
  }

  .sp-controls {
    display: flex;
    align-items: center;
    gap: 2px;
    flex-shrink: 0;
  }

  .sp-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
  }

  .sp-btn:hover:not(:disabled) {
    color: var(--text-primary);
    background: var(--hover);
  }

  .sp-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .sp-btn-main {
    background: var(--accent);
    color: #fff;
  }

  .sp-btn-main:hover:not(:disabled) {
    background: var(--accent);
    opacity: 0.9;
    color: #fff;
  }

  .sp-spinner {
    width: 12px;
    height: 12px;
    border: 2px solid rgba(255, 255, 255, 0.4);
    border-top-color: #fff;
    border-radius: 50%;
    animation: sp-spin 0.8s linear infinite;
  }

  @keyframes sp-spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
