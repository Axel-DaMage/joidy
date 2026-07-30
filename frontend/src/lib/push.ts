import { api } from './api';
import { logger } from './utils/logger';

export async function initPushNotifications(): Promise<void> {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    logger.warn('[push] Service Worker or Push API not supported');
    return;
  }

  try {
    const registration = await navigator.serviceWorker.ready;
    const existing = await registration.pushManager.getSubscription();

    if (existing) {
      await sendSubscriptionToServer(existing);
      return;
    }

    const { publicKey } = await api.push.vapidPublicKey();
    if (!publicKey) {
      logger.warn('[push] VAPID public key not configured');
      return;
    }

    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey) as unknown as ArrayBuffer,
    });

    await sendSubscriptionToServer(subscription);
  } catch (e) {
    logger.error('[push] Failed to init push notifications:', e);
  }
}

async function sendSubscriptionToServer(subscription: PushSubscription): Promise<void> {
  let keys: { p256dh: string; auth: string };

  if (subscription.getKey) {
    keys = {
      p256dh: arrayBufferToBase64(subscription.getKey('p256dh')!),
      auth: arrayBufferToBase64(subscription.getKey('auth')!),
    };
  } else {
    keys = (subscription as unknown as { keys: { p256dh: string; auth: string } }).keys;
  }

  await api.push.subscribe(subscription.endpoint, keys);
}

function arrayBufferToBase64(buffer: ArrayBuffer | null): string {
  if (!buffer) return '';
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}
