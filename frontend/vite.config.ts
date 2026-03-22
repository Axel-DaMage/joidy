import { defineConfig } from 'vite';
import { sveltekit } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 3000,
    host: '0.0.0.0'
  }
});
