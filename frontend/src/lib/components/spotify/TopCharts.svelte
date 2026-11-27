<script lang="ts">
  // Top artists / top tracks browser for /spotify (#45).
  //
  // Self-fetches both datasets lazily per active tab and caches them so
  // switching Artists↔Tracks or the time range only hits the API for the
  // changed dimension. Playback is delegated to the parent via the
  // `onPlayContext` / `onPlayUris` callbacks (single place that maps
  // 401/403/404/429 to UI states).

  import { t } from 'svelte-i18n';
  import Users from 'lucide-svelte/icons/users';
  import Music from 'lucide-svelte/icons/music';
  import Play from 'lucide-svelte/icons/play';
  import { api, type SpotifyArtist, type SpotifyTrack } from '$lib/api';
  import { formatDuration, spotifyErrorStatus } from '$lib/utils/spotify';
  import { logger } from '$lib/utils/logger';

  type TimeRange = 'short_term' | 'medium_term' | 'long_term';
  type Kind = 'artists' | 'tracks';

  interface Props {
    token?: string | null;
    onPlayContext?: (contextUri: string | null | undefined) => void;
    onPlayUris?: (uris: string[], offsetPosition?: number | null) => void;
  }

  let { token = null, onPlayContext, onPlayUris }: Props = $props();

  const TIME_RANGES: { value: TimeRange; labelKey: string }[] = [
    { value: 'short_term', labelKey: 'rangeShort' },
    { value: 'medium_term', labelKey: 'rangeMedium' },
    { value: 'long_term', labelKey: 'rangeLong' },
  ];

  let kind = $state<Kind>('artists');
  let timeRange = $state<TimeRange>('medium_term');

  let artists = $state<SpotifyArtist[]>([]);
  let tracks = $state<SpotifyTrack[]>([]);
  let loading = $state(true);
  let errorStatus = $state<number | null>(null);
  let playingId = $state<string | null>(null);

  async function load() {
    loading = true;
    errorStatus = null;
    try {
      if (kind === 'artists') {
        artists = await api.spotify.topArtists(timeRange, 20, token);
      } else {
        tracks = await api.spotify.topTracks(timeRange, 20, token);
      }
    } catch (e) {
      errorStatus = spotifyErrorStatus(e);
      logger.warn('Spotify top charts load failed:', e);
    } finally {
      loading = false;
    }
  }

  // Fetch on mount and whenever tab or range changes (the effect's first run
  // covers the initial load — no separate onMount needed).
  $effect(() => {
    kind;
    timeRange;
    load();
  });

  function pickKind(k: Kind) {
    if (k === kind) return;
    kind = k;
  }

  function pickRange(r: TimeRange) {
    if (r === timeRange) return;
    timeRange = r;
  }

  function playArtist(artist: SpotifyArtist) {
    if (!artist.uri || playingId) return;
    playingId = artist.id ?? artist.uri;
    onPlayContext?.(artist.uri);
    // Parent refreshes playback state; clear the spinner shortly after.
    setTimeout(() => (playingId = null), 1500);
  }

  function playTrack(index: number) {
    const uris = tracks.map((tr) => tr.uri).filter((u): u is string => !!u);
    const track = tracks[index];
    if (!track?.uri || uris.length === 0 || playingId) return;
    playingId = track.id ?? track.uri;
    // Play the whole chart from this index — matches Spotify's queue feel.
    onPlayUris?.(uris, index);
    setTimeout(() => (playingId = null), 1500);
  }
</script>

<section class="top-charts">
  <div class="tc-header">
    <div class="tc-tabs" role="tablist">
      <button
        class="tc-tab"
        class:active={kind === 'artists'}
        role="tab"
        aria-selected={kind === 'artists'}
        onclick={() => pickKind('artists')}
      >
        <Users size={13} /> {$t('spotify.topArtists')}
      </button>
      <button
        class="tc-tab"
        class:active={kind === 'tracks'}
        role="tab"
        aria-selected={kind === 'tracks'}
        onclick={() => pickKind('tracks')}
      >
        <Music size={13} /> {$t('spotify.topTracks')}
      </button>
    </div>
    <div class="tc-ranges">
      {#each TIME_RANGES as r}
        <button
          class="tc-range"
          class:active={timeRange === r.value}
          onclick={() => pickRange(r.value)}>{$t(`spotify.${r.labelKey}`)}</button
        >
      {/each}
    </div>
  </div>

  {#if loading}
    <div class="tc-skeleton">
      {#each Array(6) as _}
        <!-- Shared `m-skeleton` shimmer (motion system, #1657). -->
        <div class="tc-skel-row m-skeleton"></div>
      {/each}
    </div>
  {:else if errorStatus === 401}
    <p class="tc-error">{$t('spotify.sessionExpired')}</p>
  {:else if errorStatus}
    <p class="tc-error">{$t('spotify.loadError')}</p>
  {:else if kind === 'artists' && artists.length === 0}
    <p class="tc-empty">{$t('spotify.noArtists')}</p>
  {:else if kind === 'tracks' && tracks.length === 0}
    <p class="tc-empty">{$t('spotify.noTracks')}</p>
  {:else if kind === 'artists'}
    <div class="tc-artist-grid">
      {#each artists as artist, i (artist.id ?? i)}
        <button class="tc-artist" onclick={() => playArtist(artist)} disabled={!artist.uri || !!playingId}>
          <span class="tc-artist-img">
            {#if artist.image_url}
              <img src={artist.image_url} alt="" loading="lazy" />
            {:else}
              <Users size={22} />
            {/if}
            <span class="tc-play-badge"><Play size={12} /></span>
          </span>
          <span class="tc-artist-name">{artist.name ?? '—'}</span>
          {#if artist.followers != null}
            <span class="tc-artist-meta"
              >{artist.followers.toLocaleString()} {$t('spotify.followers')}</span
            >
          {/if}
        </button>
      {/each}
    </div>
  {:else}
    <div class="tc-track-list">
      {#each tracks as track, i (track.id ?? i)}
        <button
          class="tc-track"
          onclick={() => playTrack(i)}
          disabled={!track.uri || !!playingId}
          title={$t('spotify.playTrack')}
        >
          <span class="tc-track-idx">{i + 1}</span>
          <span class="tc-track-img">
            {#if track.album_image_url}
              <img src={track.album_image_url} alt="" loading="lazy" />
            {:else}
              <Music size={14} />
            {/if}
          </span>
          <span class="tc-track-info">
            <span class="tc-track-name">{track.name ?? '—'}</span>
            <span class="tc-track-sub">{track.artist_names}</span>
          </span>
          <span class="tc-track-dur">{formatDuration(track.duration_ms)}</span>
        </button>
      {/each}
    </div>
  {/if}
</section>

<style>
  .top-charts {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg, 12px);
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .tc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
  }

  .tc-tabs {
    display: flex;
    gap: 4px;
    background: var(--elevated);
    border-radius: var(--r, 8px);
    padding: 3px;
  }

  .tc-tab {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 12px;
    padding: 5px 10px;
    border-radius: 6px;
    cursor: pointer;
  }

  .tc-tab.active {
    background: var(--surface);
    color: var(--text-primary);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  }

  .tc-ranges {
    display: flex;
    gap: 4px;
  }

  .tc-range {
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    font-size: 11px;
    padding: 4px 8px;
    border-radius: 999px;
    cursor: pointer;
  }

  .tc-range.active {
    border-color: var(--accent);
    color: var(--accent);
  }

  .tc-skeleton {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  /* Gradient sweep + border-radius come from the shared `m-skeleton`
     utility (app.css); this class only keeps the geometry. */
  .tc-skel-row {
    height: 40px;
  }

  .tc-error,
  .tc-empty {
    margin: 8px 0;
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
  }

  .tc-error {
    color: var(--danger, #e05555);
  }

  .tc-artist-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
    gap: 12px;
  }

  .tc-artist {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    border: none;
    background: transparent;
    cursor: pointer;
    padding: 4px;
    border-radius: var(--r, 8px);
  }

  .tc-artist:hover:not(:disabled) {
    background: var(--hover);
  }

  .tc-artist:disabled {
    opacity: 0.6;
    cursor: default;
  }

  .tc-artist-img {
    position: relative;
    width: 72px;
    height: 72px;
    border-radius: 50%;
    overflow: hidden;
    background: var(--elevated);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
  }

  .tc-artist-img img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .tc-play-badge {
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

  .tc-artist:hover .tc-play-badge {
    opacity: 1;
  }

  .tc-artist-name {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-primary);
    text-align: center;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tc-artist-meta {
    font-size: 10px;
    color: var(--text-muted);
  }

  .tc-track-list {
    display: flex;
    flex-direction: column;
  }

  .tc-track {
    display: flex;
    align-items: center;
    gap: 10px;
    border: none;
    background: transparent;
    padding: 6px 8px;
    border-radius: var(--r, 8px);
    cursor: pointer;
    text-align: left;
    width: 100%;
  }

  .tc-track:hover:not(:disabled) {
    background: var(--hover);
  }

  .tc-track:disabled {
    opacity: 0.6;
    cursor: default;
  }

  .tc-track-idx {
    width: 20px;
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    text-align: right;
    flex-shrink: 0;
  }

  .tc-track-img {
    width: 36px;
    height: 36px;
    border-radius: 4px;
    overflow: hidden;
    background: var(--elevated);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .tc-track-img img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .tc-track-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .tc-track-name {
    font-size: 13px;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tc-track-sub {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tc-track-dur {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    flex-shrink: 0;
  }
</style>
