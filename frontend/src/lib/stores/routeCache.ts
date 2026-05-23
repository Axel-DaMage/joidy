import { writable } from 'svelte/store';
import { browser } from '$app/environment';

interface RouteCacheEntry<T> {
  data: T;
  ts: number;
}

const CACHE_TTL = 1000 * 60 * 5; // 5 minutes
const CACHE_KEY = 'joidy_route_cache';

function createRouteCache() {
  const cache = writable<Record<string, RouteCacheEntry<any>>>({});

  function load(): Record<string, RouteCacheEntry<any>> {
    if (!browser) return {};
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      const now = Date.now();
      const cleaned: Record<string, RouteCacheEntry<any>> = {};
      for (const [key, entry] of Object.entries(parsed)) {
        const e = entry as RouteCacheEntry<any>;
        if (now - e.ts < CACHE_TTL) {
          cleaned[key] = e;
        }
      }
      cache.set(cleaned);
      return cleaned;
    } catch {
      return {};
    }
  }

  function save() {
    if (!browser) return;
    let currentCache: Record<string, RouteCacheEntry<any>> = {};
    cache.subscribe(c => currentCache = c)();
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(currentCache));
    } catch {}
  }

  function get<T>(route: string): T | null {
    let result: T | null = null;
    cache.subscribe(c => {
      const entry = c[route];
      if (entry && Date.now() - entry.ts < CACHE_TTL) {
        result = entry.data as T;
      }
    })();
    return result;
  }

  function set<T>(route: string, data: T) {
    cache.update(c => ({
      ...c,
      [route]: { data, ts: Date.now() }
    }));
    save();
  }

  async function getOrFetch<T>(route: string, fetcher: () => Promise<T>): Promise<T> {
    const cached = get<T>(route);
    if (cached) {
      fetcher().then(fresh => {
        if (fresh) set(route, fresh);
      }).catch(() => {});
      return cached;
    }
    const fresh = await fetcher();
    set(route, fresh);
    return fresh;
  }

  function prefetch(routes: string[], fetcherMap: Record<string, () => Promise<any>>) {
    routes.forEach(route => {
      const fetcher = fetcherMap[route];
      if (fetcher && !get(route)) {
        fetcher().then(data => set(route, data)).catch(() => {});
      }
    });
  }

  function invalidate(route?: string) {
    if (route) {
      cache.update(c => {
        const { [route]: _, ...rest } = c;
        return rest;
      });
    } else {
      cache.set({});
    }
    save();
  }

  // Load from localStorage on init
  if (browser) {
    load();
  }

  return { cache, get, set, invalidate, load, getOrFetch, prefetch };
}

export const routeCache = createRouteCache();