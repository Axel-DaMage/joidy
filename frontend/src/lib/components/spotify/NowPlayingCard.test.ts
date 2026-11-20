import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { tick } from 'svelte';

// $app/env must be mocked before stores evaluate `browser` (jsdom provides
// localStorage via vitest.setup.ts but $app/env needs an explicit value).
vi.mock('$app/env', () => ({ browser: true, dev: false }));

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    spotify: {
      play: vi.fn(),
      pause: vi.fn(),
      next: vi.fn(),
      previous: vi.fn(),
    },
    mood: {
      today: vi.fn(),
      history: vi.fn(),
      stats: vi.fn(),
      create: vi.fn(),
    },
  },
}));

vi.mock('$lib/api', () => ({ api: apiMock }));

vi.mock('$lib/utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), log: vi.fn(), debug: vi.fn() },
}));

import NowPlayingCard from './NowPlayingCard.svelte';
import { todayMood } from '$lib/stores/mood';
import type { SpotifyPlaybackState } from '$lib/api';

function makeTrack(overrides: Record<string, unknown> = {}) {
  return {
    id: 't1',
    uri: 'spotify:track:t1',
    name: 'Song Name',
    artists: [{ id: 'a1', name: 'Artist Name', uri: 'spotify:artist:a1' }],
    artist_names: 'Artist Name',
    album: { id: 'al1', name: 'Album Name', uri: 'spotify:album:al1' },
    album_name: 'Album Name',
    album_image_url: 'https://img.example/cover.jpg',
    duration_ms: 200000,
    explicit: false,
    preview_url: null,
    is_playable: true,
    ...overrides,
  };
}

function makeState(overrides: Record<string, unknown> = {}): SpotifyPlaybackState {
  return {
    is_playing: true,
    progress_ms: 30000,
    duration_ms: 200000,
    track: makeTrack() as SpotifyPlaybackState['track'],
    context: null,
    device: { id: 'd1', name: 'Test Device', type: 'Computer', is_active: true, volume_percent: 50 },
    shuffle_state: false,
    repeat_state: 'off',
    ...overrides,
  } as SpotifyPlaybackState;
}

function apiError(status: number) {
  const err = new Error(`API PUT /integrations/spotify/play → ${status}: {}`);
  (err as Error & { status?: number }).status = status;
  return err;
}

describe('NowPlayingCard (#45)', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    todayMood.set(null);
    apiMock.mood.today.mockResolvedValue(null);
    apiMock.mood.history.mockResolvedValue([]);
    apiMock.mood.stats.mockResolvedValue({ average: 0, streak: 0, total_entries: 0, notes_correlation: 0 });
  });

  it('renders track, artists, album and progress', () => {
    const { container } = render(NowPlayingCard, {
      playback: makeState(),
      fetchedAt: Date.now(),
    });
    expect(container.querySelector('.np-title')?.textContent).toBe('Song Name');
    expect(container.textContent).toContain('Artist Name');
    expect(container.textContent).toContain('Album Name');
    expect(container.textContent).toContain('Test Device');
    const bar = container.querySelector('[role="progressbar"]');
    expect(bar).toBeTruthy();
    // The bar ticks live (progress_ms + elapsed since fetchedAt), so allow a
    // small real-time drift around the seeded 30000ms.
    const valuenow = Number(bar?.getAttribute('aria-valuenow'));
    expect(valuenow).toBeGreaterThanOrEqual(30000);
    expect(valuenow).toBeLessThan(31000);
    expect(bar?.getAttribute('aria-valuemax')).toBe('200000');
  });

  it('shows the empty state when nothing is playing', () => {
    const { container } = render(NowPlayingCard, {
      playback: makeState({ is_playing: false, track: null, progress_ms: 0, duration_ms: null }),
      fetchedAt: Date.now(),
    });
    expect(container.querySelector('.np-empty')).toBeTruthy();
    expect(container.querySelector('.np-controls')).toBeNull();
  });

  it('pause button calls api.spotify.pause with the active device', async () => {
    apiMock.spotify.pause.mockResolvedValue({ status: 'ok' });
    const onChanged = vi.fn();
    const { container } = render(NowPlayingCard, {
      playback: makeState(),
      fetchedAt: Date.now(),
      onChanged,
    });
    const main = container.querySelector('.np-btn-main') as HTMLButtonElement;
    await fireEvent.click(main);
    await tick();
    expect(apiMock.spotify.pause).toHaveBeenCalledWith('d1', null);
    expect(onChanged).toHaveBeenCalled();
  });

  it('play button resumes via api.spotify.play when paused', async () => {
    apiMock.spotify.play.mockResolvedValue({ status: 'ok' });
    const { container } = render(NowPlayingCard, {
      playback: makeState({ is_playing: false }),
      fetchedAt: Date.now(),
    });
    const main = container.querySelector('.np-btn-main') as HTMLButtonElement;
    await fireEvent.click(main);
    await tick();
    expect(apiMock.spotify.play).toHaveBeenCalledWith({ device_id: 'd1' }, null);
  });

  it('next button calls api.spotify.next', async () => {
    apiMock.spotify.next.mockResolvedValue({ status: 'ok' });
    const { container } = render(NowPlayingCard, {
      playback: makeState(),
      fetchedAt: Date.now(),
    });
    const buttons = container.querySelectorAll('.np-btn');
    await fireEvent.click(buttons[2]); // prev, play/pause, next
    await tick();
    expect(apiMock.spotify.next).toHaveBeenCalledWith('d1', null);
  });

  it('shows the Premium upsell notice on 403 (not an error toast)', async () => {
    apiMock.spotify.pause.mockRejectedValue(apiError(403));
    const { container } = render(NowPlayingCard, {
      playback: makeState(),
      fetchedAt: Date.now(),
    });
    const main = container.querySelector('.np-btn-main') as HTMLButtonElement;
    await fireEvent.click(main);
    await waitFor(() => {
      const notice = container.querySelector('.np-notice.premium');
      expect(notice).toBeTruthy();
      expect(notice?.textContent).toContain('Premium');
    });
  });

  it('shows the no-device notice on 404', async () => {
    apiMock.spotify.next.mockRejectedValue(apiError(404));
    const { container } = render(NowPlayingCard, {
      playback: makeState(),
      fetchedAt: Date.now(),
    });
    const buttons = container.querySelectorAll('.np-btn');
    await fireEvent.click(buttons[2]);
    await waitFor(() => {
      expect(container.querySelector('.np-notice')).toBeTruthy();
      expect(container.querySelector('.np-notice')?.textContent).not.toContain('Premium');
    });
  });

  it('attaches the playing track to today mood via api.mood.create', async () => {
    // Seed the mood store directly: ensureMoodLoaded() only fetches once per
    // session (module-level loadedOnce), so relying on api.mood.today here
    // would be order-dependent.
    todayMood.set({
      id: 1,
      user_id: 1,
      score: 4,
      note: 'existing note',
      entry_date: '2026-01-01',
      created_at: null,
      updated_at: null,
    });
    apiMock.mood.create.mockImplementation(async (data: { score: number; note?: string | null }) => ({
      id: 1,
      user_id: 1,
      score: data.score,
      note: data.note ?? null,
      entry_date: '2026-01-01',
      created_at: null,
      updated_at: null,
    }));
    const { container } = render(NowPlayingCard, {
      playback: makeState(),
      fetchedAt: Date.now(),
    });
    await waitFor(() => {
      expect(container.querySelector('.np-mood-btn-link')).toBeTruthy();
    });
    await fireEvent.click(container.querySelector('.np-mood-btn-link') as HTMLButtonElement);
    await waitFor(() => {
      expect(apiMock.mood.create).toHaveBeenCalled();
      const arg = apiMock.mood.create.mock.calls[0][0] as { score: number; note: string };
      expect(arg.score).toBe(4);
      expect(arg.note).toContain('existing note');
      expect(arg.note).toContain('♪ Artist Name — Song Name');
    });
  });
});
