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

// Node 22+ exposes `localStorage` on globalThis as a lazy getter that prints an
// ExperimentalWarning when *read*. We must not read the global to detect it —
// `getOwnPropertyDescriptor` inspects the property without invoking the getter.
// jsdom defines storage as a data property, Node's stub as a getter.
const isMissingOrNodeStub = (name: 'localStorage' | 'sessionStorage') => {
	const desc = Object.getOwnPropertyDescriptor(globalThis, name);
	return !desc || typeof desc.get === 'function';
};

if (isMissingOrNodeStub('localStorage')) {
	Object.defineProperty(globalThis, 'localStorage', {
		value: new MemoryStorage(),
		configurable: true,
		writable: true
	});
}

if (isMissingOrNodeStub('sessionStorage')) {
	Object.defineProperty(globalThis, 'sessionStorage', {
		value: new MemoryStorage(),
		configurable: true,
		writable: true
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
