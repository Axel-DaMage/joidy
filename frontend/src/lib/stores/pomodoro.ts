import { writable, get, derived } from 'svelte/store';
import { loadUserSettings, patchUserSettings } from '$lib/utils/userSettings';

export type Phase = 'work' | 'break' | 'longBreak';

export const LONG_MINS = 15;

export const workMins = writable(25);
export const breakMins = writable(5);
export const phase = writable<Phase>('work');
export const running = writable(false);
export const secondsLeft = writable(25 * 60);
export const pomodorosDone = writable(0);
let pomodoroPrefsReady = false;

// Derived purely for total seconds based on current phase and presets
export const totalSec = derived(
  [phase, workMins, breakMins],
  ([$phase, $workMins, $breakMins]) => {
    if ($phase === 'work') return $workMins * 60;
    if ($phase === 'break') return $breakMins * 60;
    return LONG_MINS * 60;
  }
);

workMins.subscribe(val => {
  if (!get(running) && get(phase) === 'work') secondsLeft.set(val * 60);
  if (pomodoroPrefsReady) persistPomodoroPrefs();
});
breakMins.subscribe(val => {
  if (!get(running) && get(phase) === 'break') secondsLeft.set(val * 60);
  if (pomodoroPrefsReady) persistPomodoroPrefs();
});

function clampInt(value: unknown, min: number, max: number, fallback: number): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, Math.round(n)));
}

function persistPomodoroPrefs() {
  patchUserSettings({
    pomodoro: {
      workMins: get(workMins),
      breakMins: get(breakMins),
    }
  });
}

export function initPomodoroSettings() {
  const saved = loadUserSettings().pomodoro;
  if (saved) {
    const w = clampInt(saved.workMins, 1, 180, 25);
    const b = clampInt(saved.breakMins, 1, 120, 5);
    workMins.set(w);
    breakMins.set(b);
    if (!get(running)) {
      const currentPhase = get(phase);
      if (currentPhase === 'work') secondsLeft.set(w * 60);
      if (currentPhase === 'break') secondsLeft.set(b * 60);
    }
  }
  pomodoroPrefsReady = true;
}

let timerInterval: ReturnType<typeof setInterval> | null = null;
let beepAudio: HTMLAudioElement | null = null;

export function initAudio() {
  if (typeof window !== 'undefined' && !beepAudio) {
    const beepB64 = "data:audio/mp3;base64,//O0XAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIg==";
  }
}

function playBeep() {
  if (typeof window === 'undefined') return;
  const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = 'sine';
  osc.frequency.setValueAtTime(600, ctx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(300, ctx.currentTime + 0.3);

  gain.gain.setValueAtTime(0.1, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);

  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.start();
  osc.stop(ctx.currentTime + 0.5);
}

function tick() {
  const currentSec = get(secondsLeft);
  if (currentSec > 0) {
    secondsLeft.set(currentSec - 1);
  } else {
    advance();
    playBeep();
  }
}

export function advance() {
  stopTimer();
  const currentPhase = get(phase);

  if (currentPhase === 'work') {
    const done = get(pomodorosDone) + 1;
    pomodorosDone.set(done);
    phase.set(done % 4 === 0 ? 'longBreak' : 'break');
  } else {
    phase.set('work');
  }

  secondsLeft.set(get(totalSec));
  startTimer();
}

export function startTimer() {
  if (get(running)) return;
  running.set(true);
  timerInterval = setInterval(tick, 1000);
}

export function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
  running.set(false);
}

export function toggleTimer() {
  get(running) ? stopTimer() : startTimer();
}

export function resetTimer() {
  stopTimer();
  phase.set('work');
  pomodorosDone.set(0);
  secondsLeft.set(get(workMins) * 60);
}

export function skipTimer() {
  advance();
}
