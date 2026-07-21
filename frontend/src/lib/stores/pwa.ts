import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export const deferredPrompt = writable<any>(null);
export const showInstallBanner = writable(false);
export const isAppInstalled = writable(false);

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
