<script lang="ts">
  // Recently played tracks for /spotify (#45) — compact list fed by
  // GET /me/player/recently-played. Clicking a row queues just that track
  // through the parent's `onPlayUris`.

  import { onMount } from 'svelte';
  import { t } from 'svelte-i18n';
  import History from 'lucide-svelte/icons/history';
  import Music from 'lucide-svelte/icons/music';
  import { api, type SpotifyTrack } from '$lib/api';
  import { formatPlayedAt, spotifyErrorStatus } from '$lib/utils/spotify';
  import { logger } from '$lib/utils/logger';

  interface RecentItem {
    played_at: string | null;
    track: SpotifyTrack | null;
  }

  interface Props {
    token?: string | null;
    onPlayUris?: (uris: string[], offsetPosition?: number | null) => void;
    /** Bumped by the parent to force a refetch (e.g. after OAuth connect). */
    refreshKey?: number;
  }

  let { token = null, onPlayUris, refreshKey = 0 }: Props = $props();

  const LIMIT = 15;

  let items = $state<RecentItem[]>([]);
  let loading = $state(true);
  let errorStatus = $state<number | null>(null);

  async function load() {
    loading = true;
    errorStatus = null;
    try {
      items = await api.spotify.recentlyPlayed(LIMIT, token);
    } catch (e) {
      errorStatus = spotifyErrorStatus(e);
      logger.warn('Spotify recently-played load failed:', e);
    } finally {
      loading = false;
    }
  }

  onMount(load);

  // Parent bumps refreshKey after connect/disconnect or manual refresh.
  $effect(() => {
    const key = refreshKey;
    if (key > 0) load();
  });

  function playTrack(item: RecentItem) {
    const uri = item.track?.uri;
    if (uri) onPlayUris?.([uri]);
  }
</script>

<section class="rp-section">
  <h3 class="rp-title"><History size={13} /> {$t('spotify.recentlyPlayed')}</h3>

  {#if loading}
    <div class="rp-list">
      {#each Array(5) as _}
        <div class="rp-skel"></div>
      {/each}
    </div>
  {:else if errorStatus === 401}
    <p class="rp-error">{$t('spotify.sessionExpired')}</p>
  {:else if errorStatus}
    <p class="rp-error">{$t('spotify.loadError')}</p>
  {:else if items.length === 0}
    <p class="rp-empty">{$t('spotify.noRecent')}</p>
  {:else}
    <div class="rp-list">
      {#each items as item, i (item.track?.id ?? i)}
        {#if item.track}
          <button class="rp-row" onclick={() => playTrack(item)} title={$t('spotify.playTrack')}>
            <span class="rp-img">
              {#if item.track.album_image_url}
                <img src={item.track.album_image_url} alt="" loading="lazy" />
              {:else}
                <Music size={13} />
              {/if}
            </span>
            <span class="rp-info">
              <span class="rp-name">{item.track.name ?? '—'}</span>
              <span class="rp-sub">{item.track.artist_names}</span>
            </span>
            <span class="rp-when">{formatPlayedAt(item.played_at)}</span>
          </button>
        {/if}
      {/each}
    </div>
  {/if}
</section>

<style>
  .rp-section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg, 12px);
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .rp-title {
    margin: 0;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .rp-list {
    display: flex;
    flex-direction: column;
  }

  .rp-skel {
    height: 36px;
    border-radius: var(--r, 8px);
    background: var(--elevated);
    margin-bottom: 6px;
    animation: rp-pulse 1.2s ease-in-out infinite;
  }

  @keyframes rp-pulse {
    50% {
      opacity: 0.5;
    }
  }

  .rp-error,
  .rp-empty {
    margin: 4px 0;
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
  }

  .rp-error {
    color: var(--danger, #e05555);
  }

  .rp-row {
    display: flex;
    align-items: center;
    gap: 10px;
    border: none;
    background: transparent;
    padding: 5px 8px;
    border-radius: var(--r, 8px);
    cursor: pointer;
    text-align: left;
    width: 100%;
  }

  .rp-row:hover {
    background: var(--hover);
  }

  .rp-img {
    width: 34px;
    height: 34px;
    border-radius: 5px;
    overflow: hidden;
    background: var(--elevated);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .rp-img img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .rp-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .rp-name {
    font-size: 13px;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .rp-sub {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .rp-when {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    flex-shrink: 0;
    white-space: nowrap;
  }
</style>
