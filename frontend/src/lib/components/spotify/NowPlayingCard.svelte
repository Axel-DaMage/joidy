<script lang="ts">
  // Now Playing card for the /spotify page (#45).
  //
  // Receives the normalized playback state from the parent (which owns
  // fetching) and renders art/track/album, a self-ticking progress bar,
  // transport controls and the shuffle/repeat indicators exposed by
  // GET /me/player. Playback control is Spotify-Premium gated upstream:
  // a 403 is surfaced as an inline upsell notice, never an error toast.

  import { onMount } from 'svelte';
  import { t } from 'svelte-i18n';
  import Play from 'lucide-svelte/icons/play';
  import Pause from 'lucide-svelte/icons/pause';
  import SkipBack from 'lucide-svelte/icons/skip-back';
  import SkipForward from 'lucide-svelte/icons/skip-forward';
  import Shuffle from 'lucide-svelte/icons/shuffle';
  import Repeat from 'lucide-svelte/icons/repeat';
  import Repeat1 from 'lucide-svelte/icons/repeat-1';
  import Music from 'lucide-svelte/icons/music';
  import Crown from 'lucide-svelte/icons/crown';
  import X from 'lucide-svelte/icons/x';
  import { api, type SpotifyPlaybackState } from '$lib/api';
  import { showNotification } from '$lib/stores/notifications';
  import { ensureMoodLoaded, saveMood, todayMood } from '$lib/stores/mood';
  import { formatDuration, spotifyErrorStatus } from '$lib/utils/spotify';
  import { logger } from '$lib/utils/logger';

  interface Props {
    playback: SpotifyPlaybackState | null;
    /** Timestamp (Date.now()) of when `playback` was fetched — anchors the
     *  client-side progress tick so the bar advances between refreshes. */
    fetchedAt: number;
    /** Optional X-Spotify-Token override forwarded to control endpoints. */
    token?: string | null;
    /** Called after a successful transport action so the parent refetches. */
    onChanged?: () => void;
  }

  let { playback, fetchedAt, token = null, onChanged }: Props = $props();

  const MOODS = [
    { score: 1, emoji: '😞' },
    { score: 2, emoji: '😟' },
    { score: 3, emoji: '😐' },
    { score: 4, emoji: '🙂' },
    { score: 5, emoji: '😄' },
  ];

  let busy = $state<'prev' | 'play' | 'next' | null>(null);
  let notice = $state<'premium' | 'device' | 'rate' | 'expired' | null>(null);
  let showMoodPicker = $state(false);
  let moodSaving = $state(false);

  // ── Progress bar ──────────────────────────────────────────────────────────
  // `now` only ticks while a track is actually playing, so the interval is
  // created/destroyed with playback state instead of running forever (#1311).
  let now = $state(Date.now());
  $effect(() => {
    if (!playback?.is_playing || !playback.track) return;
    const id = setInterval(() => {
      now = Date.now();
    }, 1000);
    return () => clearInterval(id);
  });

  const progressMs = $derived.by(() => {
    const base = playback?.progress_ms ?? 0;
    if (!playback?.is_playing || !fetchedAt) return base;
    const elapsed = Math.max(0, now - fetchedAt);
    const cap = playback?.duration_ms ?? Number.POSITIVE_INFINITY;
    return Math.min(base + elapsed, cap);
  });
  const progressPct = $derived(
    playback?.duration_ms ? Math.min(100, (progressMs / playback.duration_ms) * 100) : 0
  );

  // ── Transport controls ────────────────────────────────────────────────────
  async function control(kind: 'prev' | 'play' | 'next') {
    if (busy) return;
    busy = kind;
    const deviceId = playback?.device?.id ?? null;
    try {
      if (kind === 'prev') {
        await api.spotify.previous(deviceId, token);
      } else if (kind === 'next') {
        await api.spotify.next(deviceId, token);
      } else if (playback?.is_playing) {
        await api.spotify.pause(deviceId, token);
      } else {
        await api.spotify.play({ device_id: deviceId }, token);
      }
      notice = null;
      onChanged?.();
    } catch (e) {
      const status = spotifyErrorStatus(e);
      if (status === 403) {
        notice = 'premium';
      } else if (status === 404) {
        notice = 'device';
      } else if (status === 429) {
        notice = 'rate';
      } else if (status === 401) {
        notice = 'expired';
      } else {
        logger.warn('Spotify control failed:', e);
        notice = 'device';
      }
    } finally {
      busy = null;
    }
  }

  // A fresh playback fetch means earlier control errors may no longer apply.
  // Keyed on the primitive `fetchedAt` timestamp: comparing the proxied
  // `playback` object with `!==` would always mismatch ($state proxy identity)
  // and retrigger this effect forever.
  let lastFetchedAt = $state(0);
  $effect(() => {
    const ts = fetchedAt;
    if (ts && ts !== lastFetchedAt) {
      lastFetchedAt = ts;
      notice = null;
    }
  });

  // ── Mood attach (#45) ─────────────────────────────────────────────────────
  // Minimal mood↔music link: the track ref is appended to today's mood note
  // (POST /mood upserts). No dedicated backend field exists for notes/goals —
  // see the PR description for the documented gap.
  const trackRef = $derived.by(() => {
    const tr = playback?.track;
    if (!tr) return '';
    const artists = tr.artist_names || tr.artists.map((a) => a.name).filter(Boolean).join(', ');
    return `♪ ${artists} — ${tr.name ?? ''}`.trim();
  });

  onMount(() => {
    ensureMoodLoaded();
  });

  async function attachToMood(score?: number) {
    const ref = trackRef;
    if (!ref || moodSaving) return;
    moodSaving = true;
    try {
      const existing = $todayMood;
      const finalScore = score ?? existing?.score;
      if (!finalScore) {
        showMoodPicker = true;
        return;
      }
      const prevNote = existing?.note?.trim() ?? '';
      const note = prevNote ? `${prevNote}\n${ref}` : ref;
      const entry = await saveMood(finalScore, note);
      if (entry) {
        showNotification($t('spotify.moodAttached'), 'success');
        showMoodPicker = false;
      } else {
        showNotification($t('spotify.moodError'), 'error');
      }
    } finally {
      moodSaving = false;
    }
  }
</script>

<div class="np-card">
  {#if playback?.track}
    <div class="np-main">
      <div class="np-art">
        {#if playback.track.album_image_url}
          <img src={playback.track.album_image_url} alt="" loading="lazy" />
        {:else}
          <div class="np-art-fallback"><Music size={28} /></div>
        {/if}
        {#if playback.is_playing}
          <span class="np-live" title={$t('spotify.nowPlaying')}></span>
        {/if}
      </div>

      <div class="np-info">
        <div class="np-title-row">
          <h3 class="np-title">{playback.track.name ?? $t('spotify.unknownTrack')}</h3>
          {#if playback.track.explicit}<span class="np-explicit">E</span>{/if}
        </div>
        <p class="np-artists">{playback.track.artist_names || playback.track.artists.map((a) => a.name).join(', ')}</p>
        <p class="np-album">
          {playback.track.album_name ?? ''}
          {#if playback.context?.name}<span class="np-context"> · {$t('spotify.inContext', { values: { context: playback.context.name } })}</span>{/if}
        </p>
        {#if playback.device?.name}
          <p class="np-device">{$t('spotify.device', { values: { name: playback.device.name } })}</p>
        {/if}
      </div>
    </div>

    <div class="np-progress">
      <span class="np-time">{formatDuration(progressMs)}</span>
      <div
        class="np-bar"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={playback.duration_ms ?? 0}
        aria-valuenow={Math.round(progressMs)}
        aria-label={$t('spotify.progressLabel')}
      >
        <div class="np-bar-fill" style="width: {progressPct}%"></div>
      </div>
      <span class="np-time">{formatDuration(playback.duration_ms)}</span>
    </div>

    <div class="np-controls">
      <div class="np-indicators">
        <span
          class="np-indicator"
          class:active={playback.shuffle_state}
          title={$t('spotify.shuffle')}
          aria-label={$t('spotify.shuffle')}
        ><Shuffle size={14} /></span>
        {#if playback.repeat_state === 'track'}
          <span class="np-indicator active" title={$t('spotify.repeatTrack')} aria-label={$t('spotify.repeatTrack')}
            ><Repeat1 size={14} /></span
          >
        {:else}
          <span
            class="np-indicator"
            class:active={playback.repeat_state === 'context'}
            title={playback.repeat_state === 'context' ? $t('spotify.repeatContext') : $t('spotify.repeatOff')}
            aria-label={playback.repeat_state === 'context' ? $t('spotify.repeatContext') : $t('spotify.repeatOff')}
            ><Repeat size={14} /></span
          >
        {/if}
      </div>

      <div class="np-buttons">
        <button
          class="np-btn"
          onclick={() => control('prev')}
          disabled={busy !== null}
          aria-label={$t('common.previous')}
          title={$t('common.previous')}
        >
          <SkipBack size={18} />
        </button>
        <button
          class="np-btn np-btn-main"
          onclick={() => control('play')}
          disabled={busy !== null}
          aria-label={playback.is_playing ? $t('spotify.pause') : $t('spotify.play')}
          title={playback.is_playing ? $t('spotify.pause') : $t('spotify.play')}
        >
          {#if busy === 'play'}
            <span class="np-spinner"></span>
          {:else if playback.is_playing}
            <Pause size={20} />
          {:else}
            <Play size={20} />
          {/if}
        </button>
        <button
          class="np-btn"
          onclick={() => control('next')}
          disabled={busy !== null}
          aria-label={$t('common.next')}
          title={$t('common.next')}
        >
          <SkipForward size={18} />
        </button>
      </div>
      <span class="np-spacer"></span>
    </div>

    {#if notice}
      <div class="np-notice" class:premium={notice === 'premium'} role="status">
        {#if notice === 'premium'}
          <Crown size={13} />
          <span>{$t('spotify.premiumRequired')}</span>
          <a href="https://www.spotify.com/premium/" target="_blank" rel="noopener noreferrer">
            {$t('spotify.learnMore')}
          </a>
        {:else if notice === 'rate'}
          <span>{$t('spotify.rateLimited')}</span>
        {:else if notice === 'expired'}
          <span>{$t('spotify.sessionExpired')}</span>
        {:else}
          <span>{$t('spotify.noDevice')}</span>
        {/if}
        <button class="np-notice-close" onclick={() => (notice = null)} aria-label={$t('common.close')}>
          <X size={12} />
        </button>
      </div>
    {/if}

    <div class="np-mood">
      {#if showMoodPicker}
        <span class="np-mood-label">{$t('spotify.moodPick')}</span>
        <div class="np-mood-picker">
          {#each MOODS as m}
            <button
              class="np-mood-btn"
              disabled={moodSaving}
              aria-label={$t('mood.scoreLabel', { values: { score: m.score } })}
              onclick={() => attachToMood(m.score)}>{m.emoji}</button
            >
          {/each}
        </div>
      {:else}
        <button class="np-mood-btn-link" onclick={() => attachToMood()} disabled={moodSaving}>
          ♪ {#if $todayMood}{$t('spotify.moodAttach')}{:else}{$t('spotify.moodStart')}{/if}
        </button>
      {/if}
    </div>
  {:else}
    <div class="np-empty">
      <Music size={36} />
      <p class="np-empty-title">{$t('spotify.nothingPlaying')}</p>
      <p class="np-empty-hint">{$t('spotify.nothingPlayingHint')}</p>
      {#if notice === 'premium'}
        <div class="np-notice premium" role="status">
          <Crown size={13} />
          <span>{$t('spotify.premiumRequired')}</span>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .np-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg, 12px);
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .np-main {
    display: flex;
    gap: 14px;
    align-items: center;
    min-width: 0;
  }

  .np-art {
    position: relative;
    width: 96px;
    height: 96px;
    flex-shrink: 0;
    border-radius: var(--r, 8px);
    overflow: hidden;
    background: var(--elevated);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
  }

  .np-art img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .np-live {
    position: absolute;
    bottom: 6px;
    right: 6px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--success, #4caf50);
    box-shadow: 0 0 0 2px var(--surface);
  }

  .np-info {
    min-width: 0;
    flex: 1;
  }

  .np-title-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .np-title {
    margin: 0;
    font-size: 17px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .np-explicit {
    font-size: 9px;
    font-weight: 700;
    color: var(--text-muted);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 0 3px;
    flex-shrink: 0;
  }

  .np-artists,
  .np-album,
  .np-device {
    margin: 2px 0 0;
    font-size: 13px;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .np-context {
    color: var(--text-muted);
  }

  .np-device {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 4px;
  }

  .np-progress {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .np-time {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    min-width: 34px;
  }

  .np-time:last-child {
    text-align: right;
  }

  .np-bar {
    flex: 1;
    height: 4px;
    border-radius: 999px;
    background: var(--elevated);
    overflow: hidden;
  }

  .np-bar-fill {
    height: 100%;
    border-radius: 999px;
    background: var(--accent);
    transition: width 1s linear;
  }

  .np-controls {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .np-indicators {
    display: flex;
    gap: 10px;
    color: var(--text-muted);
    min-width: 64px;
  }

  .np-indicator {
    display: inline-flex;
    opacity: 0.45;
  }

  .np-indicator.active {
    opacity: 1;
    color: var(--accent);
  }

  .np-buttons {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .np-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    transition: color var(--t-fast), background var(--t-fast);
  }

  .np-btn:hover:not(:disabled) {
    color: var(--text-primary);
    background: var(--hover);
  }

  .np-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .np-btn-main {
    width: 44px;
    height: 44px;
    background: var(--accent);
    color: #fff;
  }

  .np-btn-main:hover:not(:disabled) {
    background: var(--accent);
    opacity: 0.9;
    color: #fff;
  }

  .np-spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.4);
    border-top-color: #fff;
    border-radius: 50%;
    animation: np-spin 0.8s linear infinite;
  }

  @keyframes np-spin {
    to {
      transform: rotate(360deg);
    }
  }

  .np-spacer {
    min-width: 64px;
  }

  .np-notice {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-secondary);
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r, 8px);
    padding: 8px 10px;
  }

  .np-notice.premium {
    color: var(--xp, #e8b931);
    border-color: color-mix(in srgb, var(--xp, #e8b931) 40%, transparent);
  }

  .np-notice a {
    color: var(--accent);
    margin-left: auto;
  }

  .np-notice-close {
    margin-left: auto;
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 2px;
    display: inline-flex;
  }

  .np-notice:not(:has(a)) .np-notice-close {
    margin-left: auto;
  }

  .np-mood {
    border-top: 1px solid var(--border-light, var(--border));
    padding-top: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 26px;
  }

  .np-mood-label {
    font-size: 12px;
    color: var(--text-secondary);
  }

  .np-mood-picker {
    display: flex;
    gap: 4px;
  }

  .np-mood-btn {
    background: none;
    border: none;
    font-size: 16px;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: var(--r-sm, 6px);
    opacity: 0.75;
    transition: opacity var(--t-fast), background var(--t-fast);
  }

  .np-mood-btn:hover:not(:disabled) {
    opacity: 1;
    background: var(--hover);
  }

  .np-mood-btn-link {
    background: none;
    border: none;
    color: var(--accent);
    font-size: 12px;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: var(--r-sm, 6px);
  }

  .np-mood-btn-link:hover:not(:disabled) {
    background: var(--hover);
    text-decoration: underline;
  }

  .np-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 28px 12px;
    color: var(--text-muted);
    text-align: center;
  }

  .np-empty-title {
    margin: 4px 0 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-secondary);
  }

  .np-empty-hint {
    margin: 0;
    font-size: 12px;
  }

  @media (max-width: 560px) {
    .np-art {
      width: 72px;
      height: 72px;
    }
    .np-title {
      font-size: 15px;
    }
  }
</style>
