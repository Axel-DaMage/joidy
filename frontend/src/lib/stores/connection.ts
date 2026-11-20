import { writable } from 'svelte/store';

export const isOnline = writable(true);
export const wasOffline = writable(false);

function updateOnlineStatus() {
  const online = navigator.onLine;
  isOnline.set(online);
  // wasOffline latches true on disconnect and is only cleared by the
  // consumer (the "back online" pill in +layout.svelte). Setting it from
  // the same tick as isOnline left it already false when the pill's guard
  // evaluated, so it never displayed (#1305).
  if (!online) wasOffline.set(true);
}

export function initConnectionStore() {
  updateOnlineStatus();
  window.addEventListener('online', updateOnlineStatus);
  window.addEventListener('offline', updateOnlineStatus);

  return () => {
    window.removeEventListener('online', updateOnlineStatus);
    window.removeEventListener('offline', updateOnlineStatus);
  };
}

export async function retryRequest<T>(
  fn: () => Promise<T>,
  maxRetries = 3,
  delayMs = 1000
): Promise<T> {
  let lastError: Error | null = null;

  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (e) {
      lastError = e as Error;
      if (i < maxRetries - 1) {
        // intentional: promise-based backoff delay — resolves into the awaiting
        // caller only, touches no component or store state (#1003)
        await new Promise(r => setTimeout(r, delayMs * (i + 1)));
      }
    }
  }

  throw lastError;
}