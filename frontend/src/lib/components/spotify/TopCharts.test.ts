import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, cleanup, fireEvent, waitFor } from '@testing-library/svelte';

vi.mock('$app/env', () => ({ browser: true, dev: false }));

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    spotify: {
      topArtists: vi.fn(),
      topTracks: vi.fn(),
    },
  },
}));

vi.mock('$lib/api', () => ({ api: apiMock }));

vi.mock('$lib/utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), log: vi.fn(), debug: vi.fn() },
}));

import TopCharts from './TopCharts.svelte';

const ARTISTS = [
  {
    id: 'a1',
    uri: 'spotify:artist:a1',
    name: 'Artist One',
    image_url: 'https://img.example/a1.jpg',
    genres: ['rock'],
    followers: 12345,
    popularity: 80,
  },
  {
    id: 'a2',
    uri: 'spotify:artist:a2',
    name: 'Artist Two',
    image_url: null,
    genres: [],
    followers: null,
    popularity: null,
  },
];

const TRACKS = [
  {
    id: 't1',
    uri: 'spotify:track:t1',
    name: 'Track One',
    artists: [{ id: 'a1', name: 'Artist One', uri: 'spotify:artist:a1' }],
    artist_names: 'Artist One',
    album: { id: 'al1', name: 'Album', uri: 'spotify:album:al1' },
    album_name: 'Album',
    album_image_url: 'https://img.example/t1.jpg',
    duration_ms: 210000,
    explicit: false,
    preview_url: null,
    is_playable: true,
  },
];

describe('TopCharts (#45)', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    apiMock.spotify.topArtists.mockResolvedValue(ARTISTS);
    apiMock.spotify.topTracks.mockResolvedValue(TRACKS);
  });

  it('loads top artists by default (medium_term)', async () => {
    const { container } = render(TopCharts);
    await waitFor(() => {
      expect(container.querySelectorAll('.tc-artist').length).toBe(2);
    });
    expect(apiMock.spotify.topArtists).toHaveBeenCalledWith('medium_term', 20, null);
    expect(container.textContent).toContain('Artist One');
  });

  it('switches to the tracks tab and calls topTracks', async () => {
    const { container } = render(TopCharts);
    await waitFor(() => expect(container.querySelectorAll('.tc-artist').length).toBe(2));
    const tabs = container.querySelectorAll('.tc-tab');
    await fireEvent.click(tabs[1]);
    await waitFor(() => {
      expect(container.querySelectorAll('.tc-track').length).toBe(1);
    });
    expect(apiMock.spotify.topTracks).toHaveBeenCalledWith('medium_term', 20, null);
    expect(container.textContent).toContain('Track One');
    expect(container.textContent).toContain('3:30');
  });

  it('refetches with the selected time range', async () => {
    const { container } = render(TopCharts);
    await waitFor(() => expect(container.querySelectorAll('.tc-artist').length).toBe(2));
    const ranges = container.querySelectorAll('.tc-range');
    await fireEvent.click(ranges[2]); // "Todo" / long_term
    await waitFor(() => {
      expect(apiMock.spotify.topArtists).toHaveBeenLastCalledWith('long_term', 20, null);
    });
  });

  it('plays an artist context through onPlayContext', async () => {
    const onPlayContext = vi.fn();
    const { container } = render(TopCharts, { onPlayContext });
    await waitFor(() => expect(container.querySelectorAll('.tc-artist').length).toBe(2));
    await fireEvent.click(container.querySelectorAll('.tc-artist')[0]);
    expect(onPlayContext).toHaveBeenCalledWith('spotify:artist:a1');
  });

  it('plays the track chart from the clicked index via onPlayUris', async () => {
    const onPlayUris = vi.fn();
    apiMock.spotify.topTracks.mockResolvedValue([
      TRACKS[0],
      { ...TRACKS[0], id: 't2', uri: 'spotify:track:t2', name: 'Track Two' },
    ]);
    const { container } = render(TopCharts, { onPlayUris });
    await waitFor(() => expect(container.querySelectorAll('.tc-artist').length).toBe(2));
    await fireEvent.click(container.querySelectorAll('.tc-tab')[1]);
    await waitFor(() => expect(container.querySelectorAll('.tc-track').length).toBe(2));
    await fireEvent.click(container.querySelectorAll('.tc-track')[1]);
    expect(onPlayUris).toHaveBeenCalledWith(['spotify:track:t1', 'spotify:track:t2'], 1);
  });

  it('shows the session-expired message on 401', async () => {
    const err = new Error('API GET /integrations/spotify/top-artists → 401: {}');
    (err as Error & { status?: number }).status = 401;
    apiMock.spotify.topArtists.mockRejectedValue(err);
    const { container } = render(TopCharts);
    await waitFor(() => {
      expect(container.querySelector('.tc-error')).toBeTruthy();
    });
  });
});
