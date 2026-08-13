// Vitest setup: jsdom 29 does not expose `localStorage` on the global scope by
// default (only `sessionStorage`). Several stores read/write localStorage at
// module load time, so we install an in-memory polyfill before any test runs.
class MemoryStorage implements Storage {
  private store = new Map<string, string>();
  get length() {
    return this.store.size;
  }
  clear() {
    this.store.clear();
  }
  getItem(key: string): string | null {
    return this.store.has(key) ? this.store.get(key)! : null;
  }
  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }
  removeItem(key: string) {
    this.store.delete(key);
  }
  setItem(key: string, value: string) {
    this.store.set(key, String(value));
  }
}

if (typeof globalThis.localStorage === 'undefined') {
  Object.defineProperty(globalThis, 'localStorage', {
    value: new MemoryStorage(),
    configurable: true,
    writable: true,
  });
}

if (typeof globalThis.sessionStorage === 'undefined') {
  Object.defineProperty(globalThis, 'sessionStorage', {
    value: new MemoryStorage(),
    configurable: true,
    writable: true,
  });
}

// Initialize svelte-i18n for component tests. `initI18n()` is normally called
// from the root layout, but component tests render components directly without
// mounting it, so any component using `$t()` would throw "Cannot format a
// message without first setting the initial locale" (#618).
//
// This must be a dynamic import: static `import` statements are hoisted above
// the localStorage polyfill above, and `stores/locale` reads localStorage at
// module-evaluation time via `detectLocale()`.
const { initI18n } = await import('./src/lib/i18n');
initI18n();
