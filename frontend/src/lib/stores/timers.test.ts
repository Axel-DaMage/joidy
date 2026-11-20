import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { get } from 'svelte/store';

const { apiMock, alertsMock, notifMock } = vi.hoisted(() => ({
  apiMock: {
    userSettings: {
      get: vi.fn(),
      set: vi.fn(),
    },
  },
  alertsMock: {
    fireClockAlert: vi.fn(),
    requestNotificationPermission: vi.fn(),
    stopTitleFlash: vi.fn(),
  },
  notifMock: { showNotification: vi.fn() },
}));

// Mock $app/env so `browser` is true (jsdom provides the storage APIs).
vi.mock('$app/env', () => ({ browser: true, dev: false }));
vi.mock('$lib/api', () => ({ api: apiMock }));
vi.mock('$lib/utils/clockAlerts', () => alertsMock);
vi.mock('./notifications', () => notifMock);
vi.mock('$lib/utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), log: vi.fn(), debug: vi.fn() },
}));

import {
  activeAlert,
  addMinuteToTimer,
  addTimer,
  alarms,
  deleteAlarm,
  dismissAlert,
  formatHMS,
  formatStopwatch,
  initTimersEngine,
  lapStopwatch,
  onTick,
  pauseStopwatch,
  pauseTimer,
  removeTimer,
  resetStopwatch,
  resetTimer,
  resumeTimer,
  saveAlarm,
  snoozeAlert,
  startStopwatch,
  stopwatch,
  stopwatchElapsed,
  timers,
  timersRemaining,
  toggleAlarm,
  type Alarm,
} from './timers';

/** A Date one minute ahead — alarms target the NEXT minute so a tick with
 * that exact timestamp always lands inside the alarm's minute window. */
function nextMinute(): Date {
  return new Date(Date.now() + 60_000);
}

function makeAlarm(target: Date, overrides: Partial<Alarm> = {}) {
  return {
    hour: target.getHours(),
    minute: target.getMinutes(),
    label: 'Test alarm',
    days: [] as number[],
    enabled: true,
    snoozeMinutes: 5,
    sound: 'beep' as const,
    ...overrides,
  };
}

describe('timers store (#969)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
    apiMock.userSettings.get.mockResolvedValue({ key: 'alarms', value: null });
    apiMock.userSettings.set.mockResolvedValue({ key: 'alarms', value: [] });
    // The engine is session-scoped; tests drive ticks explicitly via onTick.
    initTimersEngine();
    alarms.set([]);
    timers.set([]);
    resetStopwatch();
    activeAlert.set(null);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // ── Countdown timers ─────────────────────────────────────────────────

  it('starts a running countdown timer', () => {
    const id = addTimer('Tea', 60_000);
    const list = get(timers);
    expect(list).toHaveLength(1);
    expect(list[0].id).toBe(id);
    expect(list[0].status).toBe('running');
    expect(list[0].totalMs).toBe(60_000);
    expect(list[0].endsAt).toBeGreaterThan(Date.now());
  });

  it('pauses and resumes a timer independently', () => {
    const id = addTimer('', 60_000)!;
    vi.advanceTimersByTime(10_000);
    pauseTimer(id);

    let tm = get(timers)[0];
    expect(tm.status).toBe('paused');
    expect(tm.remainingMs).toBeLessThanOrEqual(50_000);
    expect(tm.remainingMs).toBeGreaterThan(45_000);

    resumeTimer(id);
    tm = get(timers)[0];
    expect(tm.status).toBe('running');
    expect(tm.endsAt).toBeGreaterThan(Date.now());
  });

  it('supports multiple timers in parallel with independent state', () => {
    addTimer('a', 60_000);
    addTimer('b', 120_000);
    const [a, b] = get(timers);
    pauseTimer(a.id);
    expect(get(timers)[0].status).toBe('paused');
    expect(get(timers)[1].status).toBe('running');
    expect(b.totalMs).toBe(120_000);
  });

  it('marks a timer done and fires an alert when it reaches zero', () => {
    addTimer('short', 1_000);
    vi.advanceTimersByTime(1_500);
    onTick(Date.now());

    expect(get(timers)[0].status).toBe('done');
    const alert = get(activeAlert);
    expect(alert?.kind).toBe('timer');
    expect(alertsMock.fireClockAlert).toHaveBeenCalledWith(
      expect.objectContaining({ tag: expect.stringContaining('joidy-timer-') })
    );
  });

  it('adds a minute and resets', () => {
    const id = addTimer('', 60_000)!;
    addMinuteToTimer(id);
    expect(get(timers)[0].totalMs).toBe(120_000);

    resetTimer(id);
    const tm = get(timers)[0];
    expect(tm.status).toBe('paused');
    expect(tm.remainingMs).toBe(120_000);
  });

  it('re-arms a finished timer with +1 min', () => {
    const id = addTimer('', 1_000)!;
    vi.advanceTimersByTime(1_500);
    onTick(Date.now());
    expect(get(timers)[0].status).toBe('done');

    addMinuteToTimer(id);
    const tm = get(timers)[0];
    expect(tm.status).toBe('running');
    expect(tm.endsAt).toBeGreaterThan(Date.now());
  });

  it('removes a timer', () => {
    const id = addTimer('', 60_000)!;
    removeTimer(id);
    expect(get(timers)).toHaveLength(0);
  });

  it('derives remaining ms from the tick timestamp', () => {
    const id = addTimer('', 60_000)!;
    onTick(Date.now());
    const remaining = get(timersRemaining).get(id)!;
    expect(remaining).toBeGreaterThan(55_000);

    vi.advanceTimersByTime(20_000);
    onTick(Date.now());
    expect(get(timersRemaining).get(id)!).toBeLessThanOrEqual(41_000);
  });

  // ── Alarms ───────────────────────────────────────────────────────────

  it('creates, toggles and deletes alarms', () => {
    saveAlarm(makeAlarm(nextMinute(), { days: [1, 2, 3] }));
    const [a] = get(alarms);
    expect(a.label).toBe('Test alarm');
    expect(a.days).toEqual([1, 2, 3]);

    toggleAlarm(a.id, false);
    expect(get(alarms)[0].enabled).toBe(false);

    deleteAlarm(a.id);
    expect(get(alarms)).toHaveLength(0);
  });

  it('persists alarms to the API (debounced) and localStorage cache', () => {
    saveAlarm(makeAlarm(nextMinute()));
    vi.advanceTimersByTime(500);
    expect(apiMock.userSettings.set).toHaveBeenCalledWith(
      'alarms',
      expect.arrayContaining([expect.objectContaining({ label: 'Test alarm' })])
    );
    expect(localStorage.getItem('joidy-alarms-cache-v1')).toContain('Test alarm');
  });

  it('fires a one-shot alarm at its minute and disables it', () => {
    const target = nextMinute();
    saveAlarm(makeAlarm(target, { label: 'Wake' }));
    onTick(target.getTime());

    const alert = get(activeAlert);
    expect(alert?.kind).toBe('alarm');
    expect(alert?.label).toBe('Wake');
    expect(get(alarms)[0].enabled).toBe(false);
    expect(alertsMock.fireClockAlert).toHaveBeenCalledWith(
      expect.objectContaining({ sound: 'beep' })
    );
  });

  it('does not fire a disabled alarm', () => {
    const target = nextMinute();
    saveAlarm(makeAlarm(target, { enabled: false }));
    onTick(target.getTime());
    expect(get(activeAlert)).toBeNull();
    expect(alertsMock.fireClockAlert).not.toHaveBeenCalled();
  });

  it('fires a recurring alarm only on matching weekdays', () => {
    const target = nextMinute();
    const dayInTwo = (target.getDay() + 2) % 7;
    saveAlarm(makeAlarm(target, { days: [dayInTwo] }));
    onTick(target.getTime());
    expect(get(activeAlert)).toBeNull();
  });

  it('fires a recurring alarm on a matching weekday', () => {
    const target = nextMinute();
    saveAlarm(makeAlarm(target, { days: [target.getDay()] }));
    onTick(target.getTime());
    expect(get(activeAlert)?.kind).toBe('alarm');
    // Recurring alarms stay enabled after firing.
    expect(get(alarms)[0].enabled).toBe(true);
  });

  it('snoozes a ringing alarm and fires it again', () => {
    const target = nextMinute();
    saveAlarm(makeAlarm(target, { snoozeMinutes: 5 }));
    onTick(target.getTime());
    expect(get(activeAlert)?.kind).toBe('alarm');

    snoozeAlert();
    expect(get(activeAlert)).toBeNull();
    const snoozed = get(alarms)[0].snoozedUntil;
    expect(snoozed).toBeGreaterThan(Date.now());

    vi.advanceTimersByTime(5 * 60_000 + 500);
    onTick(Date.now());
    expect(get(activeAlert)?.kind).toBe('alarm');
  });

  it('dismisses an alert and clears the snooze', () => {
    const target = nextMinute();
    saveAlarm(makeAlarm(target));
    onTick(target.getTime());
    dismissAlert();
    expect(get(activeAlert)).toBeNull();
    expect(get(alarms)[0].snoozedUntil).toBeUndefined();
  });

  // ── Stopwatch ────────────────────────────────────────────────────────

  it('counts elapsed time and records laps', () => {
    startStopwatch();
    vi.advanceTimersByTime(10_000);
    lapStopwatch();
    vi.advanceTimersByTime(5_000);
    onTick(Date.now());

    const s = get(stopwatch);
    expect(s.running).toBe(true);
    expect(s.laps).toHaveLength(1);
    expect(s.laps[0].lapMs).toBeGreaterThanOrEqual(10_000);
    expect(get(stopwatchElapsed)).toBeGreaterThanOrEqual(15_000);
  });

  it('pauses and resumes without losing elapsed time', () => {
    startStopwatch();
    vi.advanceTimersByTime(5_000);
    pauseStopwatch();
    onTick(Date.now());
    const frozen = get(stopwatchElapsed);
    expect(frozen).toBeGreaterThanOrEqual(5_000);

    vi.advanceTimersByTime(60_000);
    onTick(Date.now());
    expect(get(stopwatchElapsed)).toBe(frozen);

    startStopwatch();
    vi.advanceTimersByTime(1_000);
    onTick(Date.now());
    expect(get(stopwatchElapsed)).toBeGreaterThan(frozen);
  });

  it('resets elapsed and laps', () => {
    startStopwatch();
    vi.advanceTimersByTime(3_000);
    lapStopwatch();
    resetStopwatch();
    expect(get(stopwatchElapsed)).toBe(0);
    expect(get(stopwatch).laps).toHaveLength(0);
    expect(get(stopwatch).running).toBe(false);
  });

  // ── Formatting ───────────────────────────────────────────────────────

  it('formats countdowns as mm:ss or h:mm:ss', () => {
    expect(formatHMS(61_000)).toBe('01:01');
    expect(formatHMS(3_661_000)).toBe('1:01:01');
    expect(formatHMS(0)).toBe('00:00');
  });

  it('formats the stopwatch with centiseconds', () => {
    expect(formatStopwatch(0)).toBe('00:00.00');
    expect(formatStopwatch(61_230)).toBe('01:01.23');
    expect(formatStopwatch(3_661_000)).toBe('1:01:01.00');
  });
});
