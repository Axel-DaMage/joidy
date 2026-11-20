import { writable, get } from 'svelte/store';
import { browser } from '$app/env';
import { logger } from '$lib/utils/logger';

export const deferredPrompt = writable<any>(null);
export const showInstallBanner = writable(false);
export const isAppInstalled = writable(false);

/** A new service worker that finished installing and is waiting to activate. */
export const waitingWorker = writable<ServiceWorker | null>(null);
/** Whether the "new version available" banner is visible. */
export const showUpdateBanner = writable(false);

// Set when the user confirms an update and the new SW takes control; prevents
// a reload loop if controllerchange fires more than once.
let refreshing = false;

/**
 * Registers the service worker (production only) and wires the update flow:
 * when a new SW finishes installing while a previous one still controls the
 * page, the update banner is shown; confirming it posts `joidy:skip-waiting`
 * to the waiting worker, and the resulting `controllerchange` reloads the
 * page so no open tab keeps running stale cached assets (#1310).
 *
 * `{ type: 'module' }` is required: Kit 3 emits service-worker.js as an ESM
 * bundle with top-level imports, so a classic registration throws a
 * SyntaxError and the SW never installs.
 */
export function initServiceWorkerRegistration(): void {
  if (!browser || !('serviceWorker' in navigator) || !import.meta.env.PROD) return;

  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (refreshing) return;
    refreshing = true;
    window.location.reload();
  });

  navigator.serviceWorker
    .register('/service-worker.js', { type: 'module' })
    .then((registration) => {
      // An updated SW may already be waiting (installed while the app was
      // closed). Only offer the update when a previous SW controls this page
      // — on first install there is nothing to update.
      if (registration.waiting && navigator.serviceWorker.controller) {
        waitingWorker.set(registration.waiting);
        showUpdateBanner.set(true);
      }

      registration.addEventListener('updatefound', () => {
        const worker = registration.installing;
        if (!worker) return;
        worker.addEventListener('statechange', () => {
          if (worker.state === 'installed' && navigator.serviceWorker.controller) {
            waitingWorker.set(worker);
            showUpdateBanner.set(true);
          }
        });
      });
    })
    .catch((err) => {
      logger.warn('SW registration failed:', err);
    });
}

/** Applies a pending SW update: the waiting worker activates and the page reloads via controllerchange. */
export function applyServiceWorkerUpdate(): void {
  const worker = get(waitingWorker);
  if (worker) {
    worker.postMessage({ type: 'joidy:skip-waiting' });
  }
  showUpdateBanner.set(false);
}

if (browser) {
  const checkInstallStatus = () => {
    // If it's already installed (standalone mode)
    if (window.matchMedia('(display-mode: standalone)').matches) {
      isAppInstalled.set(true);
      showInstallBanner.set(false);
    }
  };

  checkInstallStatus();

  window.addEventListener('appinstalled', () => {
    isAppInstalled.set(true);
    showInstallBanner.set(false);
    deferredPrompt.set(null);
  });
}
