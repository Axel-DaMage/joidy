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
		setupFiles: ['./vitest.setup.ts']
	}
});
