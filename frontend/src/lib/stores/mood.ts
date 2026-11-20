import { writable } from 'svelte/store';
import { browser } from '$app/env';
import { api, type MoodEntry, type MoodStats } from '$lib/api';
import { logger } from '$lib/utils/logger';
import { SESSION_RESET_EVENT } from './session';

const EMPTY_STATS: MoodStats = {
  average: 0,
  streak: 0,
  total_entries: 0,
  notes_correlation: 0,
};

export const todayMood = writable<MoodEntry | null>(null);
export const moodHistory = writable<MoodEntry[]>([]);
export const moodStats = writable<MoodStats>({ ...EMPTY_STATS });

let loadedOnce = false;

// Drop mood state on session reset (logout / 401) so the next user on the
// same browser profile never sees the previous user's entries (#1325).
if (browser) {
  window.addEventListener(SESSION_RESET_EVENT, () => {
    todayMood.set(null);
    moodHistory.set([]);
    moodStats.set({ ...EMPTY_STATS });
    loadedOnce = false;
  });
}

/** Load today's mood, recent history, and stats in parallel. */
export async function loadMood(): Promise<void> {
  try {
    const [today, history, stats] = await Promise.all([
      api.mood.today(),
      api.mood.history(30),
      api.mood.stats(),
    ]);
    todayMood.set(today);
    moodHistory.set(history);
    moodStats.set(stats);
    loadedOnce = true;
  } catch (e) {
    logger.error('Failed to load mood data:', e);
  }
}

/** Create or update today's mood, then refresh stats + history. */
export async function saveMood(score: number, note?: string | null): Promise<MoodEntry | null> {
  try {
    const entry = await api.mood.create({ score, note: note ?? null });
    todayMood.set(entry);
    // Refresh history + stats so the widget reflects the new entry.
    const [history, stats] = await Promise.all([api.mood.history(30), api.mood.stats()]);
    moodHistory.set(history);
    moodStats.set(stats);
    return entry;
  } catch (e) {
    logger.error('Failed to save mood:', e);
    return null;
  }
}

/** Ensure mood data is loaded at least once per session. */
export async function ensureMoodLoaded(): Promise<void> {
  if (!loadedOnce) {
    await loadMood();
  }
}
