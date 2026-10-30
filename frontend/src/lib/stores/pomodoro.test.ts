import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { get } from 'svelte/store';

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    gamification: {
      pomodoro: vi.fn(),
    },
  },
}));

vi.mock('$lib/api', () => ({ api: apiMock }));

vi.mock('$lib/utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), log: vi.fn(), debug: vi.fn() },
}));

vi.mock('./gamification', () => ({
  showNotification: vi.fn(),
}));

vi.mock('$lib/utils/userSettings', () => ({
  loadUserSettings: vi.fn(() => ({})),
  patchUserSettings: vi.fn(),
}));

import { phase, resetTimer, skipTimer, startTimer, running, workMins } from './pomodoro';

const WORK_MS = 25 * 60 * 1000;
const TICK_MS = 1000;

// The first tick fires 1s after startTimer(), so a workMins-minute session
// completes after workMins*60 ticks + 1.
function finishPhase(minutes: number) {
  return vi.advanceTimersByTimeAsync(minutes * 60 * 1000 + TICK_MS);
}

describe('pomodoro XP awarding', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(HTMLAudioElement.prototype, 'play').mockResolvedValue(undefined);
    apiMock.gamification.pomodoro.mockResolvedValue({ xp_awarded: 15 });
    resetTimer();
  });

  afterEach(() => {
    resetTimer();
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it('calls the API when a work session completes naturally', async () => {
    startTimer();
    expect(get(running)).toBe(true);

    await finishPhase(25);

    expect(apiMock.gamification.pomodoro).toHaveBeenCalledTimes(1);
    expect(apiMock.gamification.pomodoro).toHaveBeenCalledWith({
      duration_minutes: 25,
      pomodoro_id: expect.any(String),
    });
    expect(get(phase)).toBe('break');
  });

  it('does not award XP when the session is skipped', () => {
    startTimer();
    vi.advanceTimersByTime(5 * 60 * 1000);

    skipTimer();

    expect(apiMock.gamification.pomodoro).not.toHaveBeenCalled();
    expect(get(phase)).toBe('break');
  });

  it('does not award XP on break completion', async () => {
    startTimer();
    await finishPhase(25);
    apiMock.gamification.pomodoro.mockClear();

    await finishPhase(5);

    expect(get(phase)).toBe('work');
    expect(apiMock.gamification.pomodoro).not.toHaveBeenCalled();
  });

  it('fails silently when the API is down', async () => {
    apiMock.gamification.pomodoro.mockRejectedValue(new Error('network down'));

    startTimer();
    await finishPhase(25);

    expect(get(phase)).toBe('break');
    expect(get(running)).toBe(true);
  });

  it('uses the configured work duration', async () => {
    workMins.set(45);
    resetTimer();
    startTimer();

    await finishPhase(45);

    expect(apiMock.gamification.pomodoro).toHaveBeenCalledWith({
      duration_minutes: 45,
      pomodoro_id: expect.any(String),
    });
  });
});
