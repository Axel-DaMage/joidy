<script lang="ts">
  // User playlists grid for /spotify (#45).
  //
  // Cards play their whole context (`spotify:playlist:…` URI) through the
  // parent's `onPlayContext`. Expanding a card lazily fetches
  // GET /playlists/{id} and lists the first tracks, each playable via
  // `onPlayUris` (queue starts at that index).

  import { onMount } from 'svelte';
  import { t } from 'svelte-i18n';
  import ListMusic from 'lucide-svelte/icons/list-music';
  import Play from 'lucide-svelte/icons/play';
  import ChevronDown from 'lucide-svelte/icons/chevron-down';
  import ChevronUp from 'lucide-svelte/icons/chevron-up';
  import Music from 'lucide-svelte/icons/music';
  import { api, type SpotifyPlaylist, type SpotifyTrack } from '$lib/api';
  import { formatDuration, spotifyErrorStatus } from '$lib/utils/spotify';
  import { logger } from '$lib/utils/logger';

  interface Props {
    token?: string | null;
    onPlayContext?: (contextUri: string | null | undefined) => void;
    onPlayUris?: (uris: string[], offsetPosition?: number | null) => void;
  }

  let { token = null, onPlayContext, onPlayUris }: Props = $props();

  const PAGE_SIZE = 20;

  let playlists = $state<SpotifyPlaylist[]>([]);
  let loading = $state(true);
  let loadingMore = $state(false);
  let errorStatus = $state<number | null>(null);
  let hasMore = $state(true);

  // Expanded playlist detail (lazy GET /playlists/{id}).
  let expandedId = $state<string | null>(null);
  let detail = $state<SpotifyPlaylist | null>(null);
  let detailLoading = $state(false);

  async function load(reset = false) {
    if (reset) {
      playlists = [];
      hasMore = true;
    }
    const offset = playlists.length;
    if (reset) loading = true;
    else loadingMore = true;
    errorStatus = null;
    try {
      const batch = await api.spotify.playlists(PAGE_SIZE, offset, token);
      playlists = reset ? batch : [...playlists, ...batch];
      hasMore = batch.length === PAGE_SIZE;
    } catch (e) {
      errorStatus = spotifyErrorStatus(e);
      logger.warn('Spotify playlists load failed:', e);
    } finally {
      loading = false;
      loadingMore = false;
    }
  }

  onMount(() => load(true));

  async function toggleDetail(playlist: SpotifyPlaylist) {
    if (!playlist.id) return;
    if (expandedId === playlist.id) {
      expandedId = null;
      detail = null;
      return;
    }
    expandedId = playlist.id;
    detail = null;
    detailLoading = true;
    try {
      detail = await api.spotify.playlist(playlist.id, token);
    } catch (e) {
      logger.warn('Spotify playlist detail failed:', e);
      expandedId = null;
    } finally {
      detailLoading = false;
    }
  }

  function playPlaylist(playlist: SpotifyPlaylist) {
    if (playlist.uri) onPlayContext?.(playlist.uri);
  }

  function playDetailTrack(index: number) {
    const tracks = (detail?.tracks ?? []).filter((tr): tr is SpotifyTrack => !!tr?.uri);
    if (!tracks.length) return;
    onPlayUris?.(tracks.map((tr) => tr.uri as string), index);
  }
</script>

<section class="pl-section">
  <h3 class="pl-title">{$t('spotify.playlists')}</h3>

  {#if loading}
    <div class="pl-grid">
      {#each Array(4) as _}
        <div class="pl-skel"></div>
      {/each}
    </div>
  {:else if errorStatus === 401}
    <p class="pl-error">{$t('spotify.sessionExpired')}</p>
  {:else if errorStatus}
    <p class="pl-error">{$t('spotify.loadError')}</p>
  {:else if playlists.length === 0}
    <p class="pl-empty">{$t('spotify.noPlaylists')}</p>
  {:else}
    <div class="pl-grid">
      {#each playlists as pl, i (pl.id ?? i)}
        <div class="pl-card" class:expanded={expandedId === pl.id}>
          <button class="pl-main" onclick={() => playPlaylist(pl)} title={$t('spotify.playPlaylist')}>
            <span class="pl-img">
              {#if pl.image_url}
                <img src={pl.image_url} alt="" loading="lazy" />
              {:else}
                <ListMusic size={20} />
              {/if}
              <span class="pl-play-badge"><Play size={13} /></span>
            </span>
            <span class="pl-info">
              <span class="pl-name">{pl.name ?? '—'}</span>
              <span class="pl-meta">
                {#if pl.owner?.display_name}<span>{$t('spotify.byOwner', { values: { owner: pl.owner.display_name } })}</span>{/if}
                {#if pl.tracks_count != null}
                  <span> · {pl.tracks_count} {$t('spotify.tracksCount')}</span>
                {/if}
              </span>
            </span>
          </button>
          <button
            class="pl-expand"
            onclick={() => toggleDetail(pl)}
            aria-expanded={expandedId === pl.id}
            aria-label={$t('spotify.toggleTracks')}
          >
            {#if expandedId === pl.id}<ChevronUp size={14} />{:else}<ChevronDown size={14} />{/if}
          </button>

          {#if expandedId === pl.id}
            <div class="pl-detail">
              {#if detailLoading}
                <p class="pl-detail-loading">{$t('spotify.loading')}</p>
              {:else if detail?.tracks && detail.tracks.length > 0}
                <div class="pl-tracks">
                  {#each detail.tracks as tr, ti (tr.id ?? ti)}
                    {#if tr?.uri}
                      <button class="pl-track" onclick={() => playDetailTrack(ti)}>
                        <Music size={12} />
                        <span class="pl-track-name">{tr.name ?? '—'}</span>
                        <span class="pl-track-dur">{formatDuration(tr.duration_ms)}</span>
                      </button>
                    {/if}
                  {/each}
                </div>
              {:else}
                <p class="pl-detail-empty">{$t('spotify.noPlaylistTracks')}</p>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>

    {#if hasMore}
      <button class="pl-more" onclick={() => load(false)} disabled={loadingMore}>
        {loadingMore ? $t('spotify.loading') : $t('spotify.loadMore')}
      </button>
    {/if}
  {/if}
</section>

<style>
  .pl-section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg, 12px);
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .pl-title {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .pl-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 10px;
  }

  .pl-skel {
    height: 64px;
    border-radius: var(--r, 8px);
    background: var(--elevated);
    animation: pl-pulse 1.2s ease-in-out infinite;
  }

  @keyframes pl-pulse {
    50% {
      opacity: 0.5;
    }
  }

  .pl-error,
  .pl-empty {
    margin: 4px 0;
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
  }

  .pl-error {
    color: var(--danger, #e05555);
  }

  .pl-card {
    border: 1px solid var(--border);
    border-radius: var(--r, 8px);
    background: var(--bg);
    overflow: hidden;
  }

  .pl-main {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    border: none;
    background: transparent;
    padding: 8px;
    cursor: pointer;
    text-align: left;
  }

  .pl-main:hover {
    background: var(--hover);
  }

  .pl-img {
    position: relative;
    width: 44px;
    height: 44px;
    border-radius: 6px;
    overflow: hidden;
    background: var(--elevated);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .pl-img img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .pl-play-badge {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.45);
    color: #fff;
    opacity: 0;
    transition: opacity var(--t-fast);
  }

  .pl-main:hover .pl-play-badge {
    opacity: 1;
  }

  .pl-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .pl-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .pl-meta {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .pl-expand {
    position: absolute;
    top: 6px;
    right: 6px;
    border: none;
    background: var(--elevated);
    color: var(--text-muted);
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .pl-card {
    position: relative;
  }

  .pl-detail {
    border-top: 1px solid var(--border-light, var(--border));
    padding: 6px 8px 8px;
    max-height: 220px;
    overflow-y: auto;
  }

  .pl-detail-loading,
  .pl-detail-empty {
    margin: 4px 0;
    font-size: 11px;
    color: var(--text-muted);
  }

  .pl-tracks {
    display: flex;
    flex-direction: column;
  }

  .pl-track {
    display: flex;
    align-items: center;
    gap: 8px;
    border: none;
    background: transparent;
    padding: 4px 6px;
    border-radius: 6px;
    cursor: pointer;
    color: var(--text-muted);
    font-size: 12px;
    text-align: left;
    width: 100%;
  }

  .pl-track:hover {
    background: var(--hover);
    color: var(--text-primary);
  }

  .pl-track-name {
    flex: 1;
    min-width: 0;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .pl-track-dur {
    font-family: var(--font-mono);
    font-size: 10px;
    flex-shrink: 0;
  }

  .pl-more {
    align-self: center;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-secondary);
    font-size: 12px;
    padding: 6px 14px;
    border-radius: 999px;
    cursor: pointer;
  }

  .pl-more:hover:not(:disabled) {
    border-color: var(--accent);
    color: var(--accent);
  }

  .pl-more:disabled {
    opacity: 0.6;
    cursor: default;
  }
</style>
