// Alert helpers for the /timers page (#969): synthesized alarm sounds,
// Web Notifications, and the mandated fallbacks — in-page banner + tab-title
// flash when notification permission is missing, vibration + visual banner
// when audio is blocked.

import { showNotification } from '$lib/stores/notifications';
import { logger } from '$lib/utils/logger';

export type AlarmSoundId = 'beep' | 'chime' | 'pulse';

export const ALARM_SOUNDS: AlarmSoundId[] = ['beep', 'chime', 'pulse'];

let audioCtx: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  try {
    if (!audioCtx) {
      const Ctor =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctor) return null;
      audioCtx = new Ctor();
    }
    if (audioCtx.state === 'suspended') {
      // resume() is async and may still reject without a user gesture —
      // callers treat a rejection as "audio blocked" and fall back.
      void audioCtx.resume();
    }
    return audioCtx;
  } catch {
    return null;
  }
}

function tone(
  ctx: AudioContext,
  freq: number,
  start: number,
  duration: number,
  type: OscillatorType = 'sine',
  peak = 0.18
) {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, ctx.currentTime + start);
  gain.gain.setValueAtTime(0.0001, ctx.currentTime + start);
  gain.gain.exponentialRampToValueAtTime(peak, ctx.currentTime + start + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + duration);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(ctx.currentTime + start);
  osc.stop(ctx.currentTime + start + duration + 0.05);
}

/**
 * Play one of the synthesized alarm presets. Returns true when audio was
 * (most likely) audible — callers vibrate + show a banner when it returns
 * false because the AudioContext is missing or still suspended.
 */
export function playAlarmSound(sound: AlarmSoundId = 'beep'): boolean {
  const ctx = getAudioContext();
  if (!ctx || ctx.state !== 'running') return false;
  try {
    switch (sound) {
      case 'chime':
        tone(ctx, 880, 0, 0.5);
        tone(ctx, 1174.66, 0.25, 0.5);
        tone(ctx, 880, 0.6, 0.4);
        tone(ctx, 1174.66, 0.85, 0.6);
        break;
      case 'pulse':
        for (let i = 0; i < 4; i++) {
          tone(ctx, 440, i * 0.35, 0.16, 'square', 0.08);
          tone(ctx, 587.33, i * 0.35 + 0.17, 0.16, 'square', 0.08);
        }
        break;
      case 'beep':
      default:
        for (let i = 0; i < 3; i++) {
          tone(ctx, 880, i * 0.5, 0.35, 'sine', 0.2);
        }
        break;
    }
    return true;
  } catch (e) {
    logger.warn('[clockAlerts] sound playback failed:', e);
    return false;
  }
}

/** Best-effort vibration — silently ignored where unsupported. */
export function vibrate(pattern: number | number[] = [200, 100, 200, 100, 300]) {
  try {
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) {
      navigator.vibrate(pattern);
    }
  } catch {
    /* unsupported */
  }
}

export function notificationsSupported(): boolean {
  return typeof window !== 'undefined' && 'Notification' in window;
}

export function notificationPermission(): NotificationPermission | 'unsupported' {
  if (!notificationsSupported()) return 'unsupported';
  return Notification.permission;
}

/** Ask for the permission once; never throws. */
export async function requestNotificationPermission(): Promise<
  NotificationPermission | 'unsupported'
> {
  if (!notificationsSupported()) return 'unsupported';
  if (Notification.permission !== 'default') return Notification.permission;
  try {
    return await Notification.requestPermission();
  } catch {
    return Notification.permission;
  }
}

// ── Tab-title flash ─────────────────────────────────────────────────────────
// Fallback for "notification permission denied/unsupported" (#969): flash the
// document title until the tab regains focus or the flash is stopped.

let titleFlashInterval: ReturnType<typeof setInterval> | null = null;
let originalTitle: string | null = null;
let titleFlashCleanupBound = false;

export function stopTitleFlash() {
  if (titleFlashInterval) {
    clearInterval(titleFlashInterval);
    titleFlashInterval = null;
  }
  if (originalTitle !== null && typeof document !== 'undefined') {
    document.title = originalTitle;
  }
  originalTitle = null;
}

export function flashTitle(text: string) {
  if (typeof document === 'undefined') return;
  stopTitleFlash();
  originalTitle = document.title;
  let on = false;
  titleFlashInterval = setInterval(() => {
    on = !on;
    document.title = on ? text : (originalTitle ?? '');
  }, 1000);
  if (!titleFlashCleanupBound) {
    titleFlashCleanupBound = true;
    // intentional: single global binding for the module lifetime (#1003)
    window.addEventListener('focus', stopTitleFlash);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') stopTitleFlash();
    });
  }
}

/**
 * Fire an alert for a finished timer/alarm:
 *  - Web Notification when permission is granted; otherwise an in-page toast
 *    (banner) plus a tab-title flash.
 *  - Alarm sound; vibration when audio is blocked.
 * Always shows the in-page toast too so nothing is lost when the OS drops
 * the notification.
 */
export function fireClockAlert(opts: {
  title: string;
  body: string;
  tag: string;
  sound: AlarmSoundId;
}) {
  const audible = playAlarmSound(opts.sound);
  if (!audible) vibrate();

  const permission = notificationPermission();
  if (permission === 'granted') {
    try {
      new Notification(opts.title, {
        body: opts.body,
        icon: '/favicon.png',
        badge: '/favicon.png',
        tag: opts.tag,
      });
    } catch (e) {
      logger.warn('[clockAlerts] Notification() failed:', e);
      flashTitle(`⏰ ${opts.title}`);
    }
  } else {
    // No permission (default/denied/unsupported) → banner + title flash.
    flashTitle(`⏰ ${opts.title}`);
    showNotification(`${opts.title} — ${opts.body}`, 'info');
    if (permission === 'default') {
      // Pre-emptively ask so the next alert can use a real notification.
      void requestNotificationPermission();
    }
  }
}
