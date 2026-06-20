import { writable } from 'svelte/store';

export const isOnline = writable(true);
export const wasOffline = writable(false);

function updateOnlineStatus() {
  const online = navigator.onLine;
  const prevOffline = !online;
  isOnline.set(online);
  wasOffline.set(prevOffline);
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
        await new Promise(r => setTimeout(r, delayMs * (i + 1)));
      }
    }
  }

  throw lastError;
}