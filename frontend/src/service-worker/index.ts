import { version } from '$app/env';
import { PUBLIC_API_PORT } from '$app/env/public';
import { assets, immutable } from '$app/manifest';
import { resolve } from '$app/paths';
import { resolveBrowserApiBase } from '../lib/utils/apiBase';

// Two caches with different lifecycles:
// - PRECACHE holds the hashed build assets + offline fallback. It is wiped and
//   rebuilt on every SW version bump.
// - RUNTIME holds same-origin, non-authed GET responses (navigations, dynamic
//   endpoints like /manifest.json, public API GETs). It is size-capped and is
//   also wiped on logout from the page side (see session.ts) so no data can
//   leak across users on a shared profile (#1310).
const PRECACHE = `joidy-precache-${version}`;
const RUNTIME = `joidy-runtime-${version}`;
const KNOWN_CACHES = [PRECACHE, RUNTIME];
const OFFLINE_URL = '/offline';
const RUNTIME_CACHE_LIMIT = 60;

// `immutable` covers the hashed Vite output, `assets` everything in `static`.
// Both are base-path-relative, so resolve them to absolute pathnames that can
// be matched against `url.pathname` in the fetch handler.
const ASSETS = [...immutable, ...assets].map((asset) => resolve(asset.path));

// The API lives on a different origin (default http://host:8000), so a
// pathname check like `/api/` can never match — resolve the real origin with
// the same helper the page uses (lib/utils/apiBase.ts). Kit 3 loads dynamic
// public env in service workers at runtime via /_app/env.js (see the
// vite-plugin-sveltekit-service-worker-env prelude), so a port-fallback'd
// PUBLIC_API_PORT resolves correctly here too (#1487). `self.location` is the
// SW scope origin — same host the page resolves against.
const API_ORIGIN = new URL(
  resolveBrowserApiBase(
    PUBLIC_API_PORT,
    import.meta.env.VITE_API_URL as string | undefined,
    self.location
  )
).origin;

self.addEventListener('install', (event) => {
  async function addFilesToCache() {
    const cache = await caches.open(PRECACHE);
    // Per-asset guard: a single failed asset must not reject the whole
    // install (cache.addAll is atomic-fragile).
    await Promise.all(
      ASSETS.map((asset) =>
        cache.add(asset).catch(() => {
          // Asset missing or network hiccup — it will be cached lazily on
          // first fetch via cacheFirst instead of bricking the install.
        })
      )
    );
    // Cache the offline fallback page explicitly.
    try {
      const offlineResponse = await fetch(OFFLINE_URL);
      if (offlineResponse.ok) {
        await cache.put(OFFLINE_URL, offlineResponse.clone());
      }
    } catch {
      // Offline page may not be available during dev; it will still be fetched on demand.
    }
  }
  event.waitUntil(addFilesToCache());
  // NOTE: no unconditional self.skipWaiting() here. The new SW waits until
  // the page posts 'joidy:skip-waiting' (user-confirmed update banner).
  // Activating mid-session would wipe caches out from under open pages and
  // break pending lazy import()s (#1310).
});

self.addEventListener('activate', (event) => {
  async function activate() {
    // Version bump: drop every cache that is not the current precache/runtime
    // pair — including legacy `joidy-cache-*` entries that may hold responses
    // cached before authed requests were excluded.
    for (const key of await caches.keys()) {
      if (!KNOWN_CACHES.includes(key)) {
        await caches.delete(key);
      }
    }
    await self.clients.claim();
  }
  event.waitUntil(activate());
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  const isApiRequest = url.origin === API_ORIGIN;

  // Only intercept same-origin requests and calls to the API origin.
  // Everything else (cross-origin APIs, websockets, dev paths) is left to
  // the browser untouched.
  if (url.origin !== self.location.origin && !isApiRequest) return;

  if (!url.protocol.startsWith('http')) return;

  if (
    url.pathname.startsWith('/@') ||
    url.pathname.startsWith('/node_modules/') ||
    url.pathname.startsWith('/src/')
  ) {
    return;
  }

  if (isApiRequest) {
    // Requests carrying credentials are never cached and never served from
    // cache — otherwise one user's data could be served to the next user of
    // the same browser profile. Let them hit the network directly.
    if (event.request.headers.has('authorization')) return;
    event.respondWith(apiNetworkFirst(event.request));
    return;
  }

  if (ASSETS.includes(url.pathname) || url.pathname.startsWith('/_app/')) {
    event.respondWith(cacheFirst(event.request));
    return;
  }

  if (event.request.mode === 'navigate') {
    event.respondWith(navigateWithOfflineFallback(event.request));
    return;
  }

  event.respondWith(networkWithCacheFallback(event.request));
});

async function cacheFirst(request: Request): Promise<Response> {
  const cache = await caches.open(PRECACHE);
  const cached = await cache.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Offline', { status: 503 });
  }
}

// Whether a public (unauthed) API response is safe to keep in the runtime
// cache. Honors `Vary: Authorization`/`*` and `Cache-Control: no-store|private`
// so endpoints that vary by user are never persisted.
function isCacheableApiResponse(response: Response): boolean {
  if (!response.ok) return false;
  const vary = (response.headers.get('vary') ?? '').toLowerCase();
  if (vary.includes('authorization') || vary.includes('*')) return false;
  const cacheControl = (response.headers.get('cache-control') ?? '').toLowerCase();
  if (cacheControl.includes('no-store') || cacheControl.includes('private')) return false;
  return true;
}

// Network-first for public API GETs: fresh data when online, cached fallback
// offline. Unlike the old `networkFirst`, this one actually populates the
// cache, so the offline `cache.match` fallback can hit.
async function apiNetworkFirst(request: Request): Promise<Response> {
  const cache = await caches.open(RUNTIME);
  try {
    const response = await fetch(request);
    if (isCacheableApiResponse(response)) {
      cache.put(request, response.clone());
      trimCache(RUNTIME, RUNTIME_CACHE_LIMIT);
    }
    return response;
  } catch {
    const cached = await cache.match(request);
    return cached || new Response('Offline', { status: 503 });
  }
}

async function networkWithCacheFallback(request: Request): Promise<Response> {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(RUNTIME);
      cache.put(request, response.clone());
      trimCache(RUNTIME, RUNTIME_CACHE_LIMIT);
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response('Offline', { status: 503 });
  }
}

async function navigateWithOfflineFallback(request: Request): Promise<Response> {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(RUNTIME);
      cache.put(request, response.clone());
      trimCache(RUNTIME, RUNTIME_CACHE_LIMIT);
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    const offlinePage = await caches.match(OFFLINE_URL);
    if (offlinePage) return offlinePage;
    return new Response('Offline', { status: 503 });
  }
}

// Bounded runtime cache: evict oldest entries (CacheStorage.keys() preserves
// insertion order) once the cap is exceeded so visited pages and dynamic
// GETs cannot grow it without limit.
async function trimCache(cacheName: string, maxItems: number): Promise<void> {
  try {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();
    const excess = keys.length - maxItems;
    for (let i = 0; i < excess; i++) {
      await cache.delete(keys[i]);
    }
  } catch {
    /* best-effort eviction */
  }
}

self.addEventListener('push', (event) => {
  // Non-JSON push payloads used to throw in .json() and silently drop the
  // notification — parse defensively and fall back to the raw text.
  async function handlePush() {
    let data: { title?: string; body?: string; url?: string } = {};
    try {
      data = event.data?.json() ?? {};
    } catch {
      try {
        const text = await event.data?.text();
        if (text) data = { body: text };
      } catch {
        /* keep the default notification */
      }
    }

    const title = data.title || 'Joidy';
    await self.registration.showNotification(title, {
      body: data.body || 'Nueva notificación',
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      vibrate: [200, 100, 200],
      data: { url: data.url || '/' },
    });
  }
  event.waitUntil(handlePush());
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data as { url?: string } | undefined)?.url || '/';
  event.waitUntil(
    (async () => {
      // Focus an existing app window when possible instead of always
      // opening a new one; fall back to openWindow with the payload URL.
      const clientList = (await self.clients.matchAll({
        type: 'window',
        includeUncontrolled: true,
      })) as WindowClient[];
      const client = clientList.find((c) => 'focus' in c);
      if (client) {
        await client.focus();
        try {
          await client.navigate(url);
        } catch {
          /* navigate may fail; the focus still applied */
        }
      } else {
        await self.clients.openWindow(url);
      }
    })()
  );
});

// ── Background Sync ───────────────────────────────────────────────────────────
// When supported, register a sync tag so the browser retries pending outbox
// changes once connectivity is restored (even if the page is closed). On the
// sync event we postMessage all controlled clients so they call processOutbox.

const SYNC_TAG = 'joidy-outbox-sync';

self.addEventListener('message', (event) => {
  const type = event.data?.type;
  // User confirmed the "update available" banner — activate the waiting SW.
  if (type === 'joidy:skip-waiting') {
    event.waitUntil(self.skipWaiting());
  }
  // Page requested a full cache wipe (e.g. on logout/session reset).
  if (type === 'joidy:clear-caches') {
    event.waitUntil(clearAllCaches());
  }
  // Allow the page to request a Background Sync registration.
  if (type === 'joidy:register-sync') {
    registerBackgroundSync();
  }
});

async function clearAllCaches(): Promise<void> {
  for (const key of await caches.keys()) {
    if (key.startsWith('joidy-')) {
      await caches.delete(key);
    }
  }
}

async function registerBackgroundSync(): Promise<void> {
  try {
    if ('sync' in self.registration) {
      await self.registration.sync.register(SYNC_TAG);
    }
  } catch {
    // Background Sync may be unavailable (e.g. iOS Safari); ignore silently.
  }
}

self.addEventListener('sync', (event) => {
  if (event.tag === SYNC_TAG) {
    event.waitUntil(notifyClientsToSync());
  }
});

async function notifyClientsToSync(): Promise<void> {
  const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  for (const client of clients) {
    client.postMessage({ type: 'joidy:sync' });
  }
}
