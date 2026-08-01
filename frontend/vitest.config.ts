import { defineConfig } from 'vitest/config';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
	plugins: [sveltekit()],
	// Ensure Svelte resolves to the browser (client) build so that
	// `svelte.mount` is available when rendering components with
	// @testing-library/svelte in the jsdom environment.
	resolve: {
		conditions: ['browser']
	},
	test: {
		include: ['src/**/*.{test,spec}.{js,ts}'],
		environment: 'jsdom',
		setupFiles: ['./vitest.setup.ts'],
		coverage: {
			provider: 'v8',
			include: ['src/lib/stores/**', 'src/lib/utils/**'],
			exclude: ['**/*.d.ts', '**/*.test.ts', 'src/lib/stores/index.ts'],
			thresholds: {
				lines: 25,
				functions: 25,
				statements: 24,
				branches: 20
			},
			reporter: ['text', 'html']
		}
	}
});
