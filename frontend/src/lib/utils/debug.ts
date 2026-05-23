import { devMode } from '$lib/stores/settings';

export function debugLog(...args: unknown[]) {
  if (typeof window !== 'undefined' && devMode) {
    console.log('[DEBUG]', new Date().toISOString(), ...args);
  }
}

export function debugWarn(...args: unknown[]) {
  if (typeof window !== 'undefined' && devMode) {
    console.warn('[WARN]', new Date().toISOString(), ...args);
  }
}

export function debugError(...args: unknown[]) {
  if (typeof window !== 'undefined' && devMode) {
    console.error('[ERROR]', new Date().toISOString(), ...args);
  }
}

export function debugGroup(label: string) {
  if (typeof window !== 'undefined' && devMode) {
    console.group(`[DEBUG] ${label}`);
  }
}

export function debugGroupEnd() {
  if (typeof window !== 'undefined' && devMode) {
    console.groupEnd();
  }
}

export function captureAndLog(error: Error, context?: string) {
  const msg = context ? `[${context}] ${error.message}` : error.message;
  debugError(msg, error.stack);
  return msg;
}

window.addEventListener('error', (e) => {
  if (typeof window !== 'undefined' && (devMode as unknown as { subscribe: (fn: (v: boolean) => void) => void }).subscribe) {
    devMode.subscribe(enabled => {
      if (enabled) {
        console.error('[UNCAUGHT]', e.message, e.filename, e.lineno);
      }
    })();
  }
});

window.addEventListener('unhandledrejection', (e) => {
  if (typeof window !== 'undefined') {
    devMode.subscribe(enabled => {
      if (enabled) {
        console.error('[UNHANDLED REJECTION]', e.reason);
      }
    })();
  }
});