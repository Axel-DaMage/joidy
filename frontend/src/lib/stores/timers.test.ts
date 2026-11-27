import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { get } from 'svelte/store';

const { apiMock, alertsMock, notifMock, gamificationMock } = vi.hoisted(() => ({
  apiMock: {
    userSettings: {
      get: vi.fn(),
      set: vi.fn(),
    },
    gamification: {
      pomodoro: vi.fn(),
    },
  },
  alertsMock: {
    fireClockAlert: vi.fn(),
    requestNotificationPermission: vi.fn(),
    stopTitleFlash: vi.fn(),
  },
  notifMock: { showNotification: vi.fn() },
  gamificationMock: { applyStats: vi.fn(), showXPGain: vi.fn() },
}));

// Mock $app/env so `browser` is true (jsdom provides the storage APIs).
vi.mock('$app/env', () => ({ browser: true, dev: false }));
vi.mock('$lib/api', () => ({ api: apiMock }));
vi.mock('$lib/utils/clockAlerts', () => alertsMock);
vi.mock('./notifications', () => notifMock);
vi.mock('./gamification', () => gamificationMock);
vi.mock('$lib/utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), log: vi.fn(), debug: vi.fn() },
}));

import {
  activeAlert,
  addMinuteToTimer,
  addTimer,
  alarmGroups,
  alarms,
  deleteAlarm,
  dismissAlert,
  formatDurationShort,
  formatHMS,
  formatSignedDelta,
  formatStopwatch,
  initTimersEngine,
  lapStopwatch,
  nextAlarm,
  nextAlarmFireAt,
  nextTimer,
  onTick,
  pauseStopwatch,
  pauseTimer,
  removeTimer,
  resetStopwatch,
  resetTimer,
  restartTimer,
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

  // ── Timer metadata & lifecycle (#1663) ───────────────────────────────

  it('stores creation metadata: color, links, XP and repeat flags', () => {
    const id = addTimer('Focus', 25 * 60_000, {
      color: '#ff8800',
      goalId: 3,
      noteId: 7,
      awardXp: true,
      repeat: true,
    });
    const tm = get(timers).find((x) => x.id === id)!;
    expect(tm.color).toBe('#ff8800');
    expect(tm.goalId).toBe(3);
    expect(tm.noteId).toBe(7);
    expect(tm.awardXp).toBe(true);
    expect(tm.repeat).toBe(true);
  });

  it('restarts a finished timer with its full duration', () => {
    const id = addTimer('Tea', 1_000)!;
    vi.advanceTimersByTime(1_500);
    onTick(Date.now());
    expect(get(timers)[0].status).toBe('done');
    dismissAlert();

    restartTimer(id);
    const tm = get(timers)[0];
    expect(tm.status).toBe('running');
    expect(tm.remainingMs).toBe(tm.totalMs);
    expect(tm.endsAt).toBeGreaterThan(Date.now());
  });

  it('re-arms a repeating timer instead of marking it done', () => {
    addTimer('Interval', 1_000, { repeat: true });
    vi.advanceTimersByTime(1_500);
    onTick(Date.now());

    const tm = get(timers)[0];
    expect(tm.status).toBe('running');
    expect(tm.endsAt).toBeGreaterThan(Date.now());
    // The cycle alert still fires every round.
    expect(get(activeAlert)?.kind).toBe('timer');
  });

  it('requests XP via the pomodoro event for completed focus timers', () => {
    apiMock.gamification.pomodoro.mockResolvedValue({ xp_awarded: 15 });
    addTimer('Focus', 25 * 60_000, { awardXp: true });
    vi.advanceTimersByTime(25 * 60_000 + 500);
    onTick(Date.now());

    expect(apiMock.gamification.pomodoro).toHaveBeenCalledWith(
      expect.objectContaining({ duration_minutes: 25 })
    );
  });

  it('does not request XP when the flag is off', () => {
    addTimer('Tea', 1_000);
    vi.advanceTimersByTime(1_500);
    onTick(Date.now());
    expect(apiMock.gamification.pomodoro).not.toHaveBeenCalled();
  });

  it('exposes the soonest-finishing running timer', () => {
    addTimer('long', 120_000);
    const shortId = addTimer('short', 60_000)!;
    onTick(Date.now());
    expect(get(nextTimer)?.timer.id).toBe(shortId);

    pauseTimer(shortId);
    onTick(Date.now());
    expect(get(nextTimer)?.timer.label).toBe('long');
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

  // ── Next-fire scheduling (#1663) ─────────────────────────────────────

  it('computes nextAlarmFireAt for a one-shot alarm later today', () => {
    const from = Date.now();
    const target = new Date(from + 2 * 3600_000);
    const a = { ...makeAlarm(target), id: 'al-x' };
    const at = nextAlarmFireAt(a, from);
    expect(at).toBeGreaterThan(from);
    expect(at).toBeLessThanOrEqual(from + 2 * 3600_000 + 60_000);
    expect(new Date(at!).getHours()).toBe(target.getHours());
    expect(new Date(at!).getMinutes()).toBe(target.getMinutes());
  });

  it('rolls a past one-shot alarm over to tomorrow', () => {
    const from = Date.now();
    const past = new Date(from - 60_000);
    const a = { ...makeAlarm(past), id: 'al-x' };
    const at = nextAlarmFireAt(a, from)!;
    expect(at).toBeGreaterThan(from);
    // Next occurrence is within the next 24h.
    expect(at).toBeLessThanOrEqual(from + 24 * 3600_000);
  });

  it('returns null for a disabled alarm and honors snoozedUntil', () => {
    const from = Date.now();
    const target = new Date(from + 3600_000);
    const disabled = { ...makeAlarm(target, { enabled: false }), id: 'al-x' };
    expect(nextAlarmFireAt(disabled, from)).toBeNull();

    const snoozed = { ...disabled, snoozedUntil: from + 10 * 60_000 };
    expect(nextAlarmFireAt(snoozed, from)).toBe(from + 10 * 60_000);
  });

  it('picks the first matching weekday for recurring alarms', () => {
    const from = Date.now();
    const target = new Date(from + 2 * 3600_000);
    const otherDay = (target.getDay() + 3) % 7;
    const a = { ...makeAlarm(target, { days: [otherDay] }), id: 'al-x' };
    const at = nextAlarmFireAt(a, from)!;
    expect(at).toBeGreaterThan(from);
    expect(new Date(at).getDay()).toBe(otherDay);
  });

  it('groups alarms into upcoming (by next fire) and inactive', () => {
    const soon = makeAlarm(nextMinute(), { label: 'soon' });
    const later = makeAlarm(new Date(Date.now() + 2 * 60_000), { label: 'later' });
    const off = makeAlarm(nextMinute(), { label: 'off', enabled: false });
    saveAlarm(later);
    saveAlarm(soon);
    saveAlarm(off);
    onTick(Date.now());

    const groups = get(alarmGroups);
    expect(groups.upcoming.map((e) => e.alarm.label)).toEqual(['soon', 'later']);
    expect(groups.inactive.map((a) => a.label)).toEqual(['off']);
    expect(get(nextAlarm)?.alarm.label).toBe('soon');
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

  it('formats relative durations compactly', () => {
    expect(formatDurationShort(45_000)).toBe('45s');
    expect(formatDurationShort(45 * 60_000)).toBe('45m');
    expect(formatDurationShort((7 * 60 + 23) * 60_000)).toBe('7h 23m');
    expect(formatDurationShort(2 * 3600_000)).toBe('2h');
    expect(formatDurationShort(0)).toBe('1s');
  });

  it('formats signed lap deltas', () => {
    expect(formatSignedDelta(2400)).toBe('+2.4s');
    expect(formatSignedDelta(-800)).toBe('-0.8s');
    expect(formatSignedDelta(10)).toBe('±0.0s');
  });
});
